"""
backend/main.py
================
FastAPI server for the AI Refactoring Pipeline.

API Endpoints (v1)
------------------
POST   /api/v1/refactor              — Upload files (single .py, multiple .py,
                                       folder via browser, or .zip archive)
GET    /api/v1/status/{job_id}       — Poll job status + current pipeline stage
GET    /api/v1/results/{job_id}      — Retrieve refactored code + validation report
GET    /api/v1/jobs                  — List all job history
GET    /health                       — Health check
WS     /api/v1/ws/{job_id}          — WebSocket for real-time stage updates

Upload modes
------------
1. Single   .py  — classic single-file refactor
2. Multiple .py  — any number of .py files (browser multi-select or webkitdirectory)
3. .zip archive  — extracted server-side; all .py files inside are processed
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import signal
import subprocess
import sys
import threading
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, List

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware

# ─────────────────────────────────────────────────────────────────────────────
# App setup
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AI Refactoring Pipeline API",
    description="REST API for async code refactoring via LLM pipeline.",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR   = Path(__file__).parent.resolve()
UPLOAD_DIR = BASE_DIR / "input" / "uploads"
OUTPUT_DIR = BASE_DIR / "output"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

_executor = ThreadPoolExecutor(max_workers=4)

# ─────────────────────────────────────────────────────────────────────────────
# Job Store (in-memory)
# ─────────────────────────────────────────────────────────────────────────────

STAGE_LABELS = {
    0: "idle",
    1: "cAST",
    2: "prompt_builder",
    3: "llm_agent",
    4: "validator",
    5: "done",
}

_jobs: dict[str, dict[str, Any]] = {}
_ws_connections: dict[str, list[WebSocket]] = {}
_ws_lock = threading.Lock()

# Track active subprocesses for cancellation
_active_processes: dict[str, subprocess.Popen] = {}
_proc_lock = threading.Lock()


def _new_job(job_id: str, filenames: list[str], config: dict) -> dict:
    return {
        "job_id":      job_id,
        "filename":    ", ".join(filenames),   # display label
        "filenames":   filenames,
        "config":      config,
        "stage":       0,
        "stage_label": "idle",
        "status":      "queued",
        "created_at":  datetime.now(timezone.utc).isoformat(),
        "updated_at":  datetime.now(timezone.utc).isoformat(),
        "stage_times": {},
        "stdout":      "",
        "stderr":      "",
        "exit_code":   None,
        "refactored_code":    None,
        "validation_report":  None,
        "per_file_results":   [],    # populated for multi-file jobs
        "error":       None,
    }


def _update_job(job_id: str, **kwargs) -> None:
    _jobs[job_id].update(kwargs)
    _jobs[job_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
    _broadcast(job_id, _jobs[job_id])


def _broadcast(job_id: str, payload: dict) -> None:
    with _ws_lock:
        clients = list(_ws_connections.get(job_id, []))
    for ws in clients:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(ws.send_json(payload), loop)
        except Exception:
            pass


def _kill_process_tree(proc: subprocess.Popen) -> None:
    """Kill a process and its children."""
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    else:
        try:
            import psutil
            parent = psutil.Process(proc.pid)
            for child in parent.children(recursive=True):
                child.terminate()
            parent.terminate()
        except ImportError:
            proc.kill()


# ─────────────────────────────────────────────────────────────────────────────
# File helpers
# ─────────────────────────────────────────────────────────────────────────────

def _collect_py_files(job_dir: Path) -> list[Path]:
    """Return all .py files recursively inside *job_dir*."""
    return sorted(job_dir.rglob("*.py"))


async def _save_uploads(
    files: list[UploadFile], job_dir: Path,
) -> list[Path]:
    """
    Save every uploaded file into *job_dir*, preserving directory structure.

    Handles three cases:
    - .zip   → extract all .py files, preserving internal directory layout
    - .py    → save directly, preserving the relative path sent by the browser
              (folder uploads via webkitdirectory send "dir/sub/file.py")
    - other  → ignored with a warning
    Returns the list of saved .py paths.
    """
    job_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []

    for uf in files:
        contents = await uf.read()
        name = uf.filename or "upload"

        if name.endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(contents)) as zf:
                    for member in zf.namelist():
                        # Skip directories, __pycache__, hidden files
                        if (member.endswith("/")
                            or "__pycache__" in member
                            or member.startswith("__")
                            or not member.endswith(".py")):
                            continue
                        # Security: reject path-traversal attempts
                        resolved = (job_dir / member).resolve()
                        if not str(resolved).startswith(str(job_dir.resolve())):
                            continue
                        # Preserve the full internal directory tree
                        dest = job_dir / member
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(zf.read(member))
                        saved.append(dest)
            except zipfile.BadZipFile:
                pass  # skip malformed zips
        elif name.endswith(".py"):
            # Preserve the full relative path from the browser
            # (webkitdirectory sends e.g. "myproject/utils/helpers.py")
            rel = Path(name)
            dest = job_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(contents)
            saved.append(dest)
        # Other types silently ignored

    return saved


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline runner (background thread)
# ─────────────────────────────────────────────────────────────────────────────

def _advance_stage(job_id: str, stage: int) -> None:
    if job_id not in _jobs: return
    now = datetime.now(timezone.utc).isoformat()
    # We update the dictionary directly to avoid race conditions with stage_times
    _jobs[job_id]["stage_times"][stage] = now
    _update_job(job_id, stage=stage, stage_label=STAGE_LABELS[stage], status="running")


def _run_pipeline(job_id: str, py_files: list[Path], config: dict) -> None:
    """Run orchestrate.py against one or more .py files."""
    # Create job-specific output directory
    job_output_dir = OUTPUT_DIR / job_id
    job_output_dir.mkdir(parents=True, exist_ok=True)
    
    _advance_stage(job_id, 1)

    cmd = [
        sys.executable,
        str(BASE_DIR / "orchestrate.py"),
        *[str(f) for f in py_files],
        "--model",      config["model"],
        "--batch-size", str(config["batch_size"]),
        "--delay",      str(config["delay"]),
        "--output-dir", str(job_output_dir),
    ]
    if config.get("in_place"):
        cmd.append("--in-place")
    if config.get("no_functional"):
        cmd.append("--no-functional")

    # Subprocess execution
    full_stdout = []
    full_stderr = []

    def read_stream(stream, collection, is_stdout=False):
        """Read lines from a stream and detect stage markers."""
        try:
            for line in iter(stream.readline, ""):
                if not line: break
                collection.append(line)
                if is_stdout and "::STAGE::" in line:
                    try:
                        parts = line.strip().split("::")
                        if len(parts) >= 3:
                            # Extract stage number (can be float, e.g. 3.5)
                            s_num = float(parts[2])
                            # Extract optional label
                            s_label = parts[3] if len(parts) >= 4 else STAGE_LABELS.get(int(s_num), "running")
                            
                            # Record the exact timestamp for this stage advancement
                            now_iso = datetime.now(timezone.utc).isoformat()
                            
                            # Update job state
                            with _ws_lock:
                                if job_id in _jobs:
                                    _jobs[job_id]["stage"] = s_num
                                    _jobs[job_id]["stage_label"] = s_label
                                    _jobs[job_id]["stage_times"][str(s_num)] = now_iso
                                    _jobs[job_id]["updated_at"] = now_iso
                            
                            _broadcast(job_id, _jobs[job_id])
                    except Exception as e:
                        print(f"[WS] Error parsing stage marker: {e}")
        except Exception:
            pass

    try:
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        
        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(BASE_DIR),
            env=env,
            creationflags=creation_flags,
        )
        
        with _proc_lock:
            _active_processes[job_id] = process
            
        # Start monitoring threads
        t_out = threading.Thread(target=read_stream, args=(process.stdout, full_stdout, True), daemon=True)
        t_err = threading.Thread(target=read_stream, args=(process.stderr, full_stderr, False), daemon=True)
        t_out.start(); t_err.start()

        try:
            # Wait for completion or timeout
            # We use wait() because we are reading streams in threads
            process.wait(timeout=1800)
        except subprocess.TimeoutExpired:
            _kill_process_tree(process)
            process.wait()
            raise
        finally:
            with _proc_lock:
                _active_processes.pop(job_id, None)
            # Ensure threads finish
            t_out.join(timeout=2.0)
            t_err.join(timeout=2.0)

        stdout = "".join(full_stdout)
        stderr = "".join(full_stderr)

        # Check if we were cancelled
        if _jobs.get(job_id, {}).get("status") == "cancelled":
            return

    except subprocess.TimeoutExpired:
        _update_job(job_id, stage=0, stage_label="idle", status="failed",
                    error="Pipeline timed out after 30 minutes. Large projects or API rate limits may be the cause.")
        return
    except Exception as exc:
        _update_job(job_id, stage=0, stage_label="idle", status="failed",
                    error=str(exc))
        return

    for t in (t2, t3, t4): t.cancel()

    # Collect per-file artefacts
    per_file: list[dict] = []
    primary_code: str | None = None
    primary_report: dict = {}

    job_output_dir = OUTPUT_DIR / job_id

    for py_path in py_files:
        stem = py_path.stem
        refactored_file = job_output_dir / f"{stem}.refactored.py"
        report_json     = job_output_dir / f"{stem}_validation_report.json"

        code = refactored_file.read_text(encoding="utf-8") if refactored_file.exists() else None
        report: dict = {}
        if report_json.exists():
            try:
                report = json.loads(report_json.read_text(encoding="utf-8"))
            except Exception:
                pass

        entry = {
            "filename":          py_path.name,
            "original_code":     py_path.read_text(encoding="utf-8", errors="replace"),
            "refactored_code":   code,
            "validation_report": report,
        }
        per_file.append(entry)

        # Use first file as the "primary" result for backwards compat
        if primary_code is None and code:
            primary_code = code
            primary_report = report

    final_status = "completed" if process.returncode == 0 else "failed"
    
    # Check if job was cancelled during the final moments
    if _jobs.get(job_id, {}).get("status") == "cancelled":
        return

    now_ts = datetime.now(timezone.utc)
    now    = now_ts.isoformat()

    if job_id in _jobs:
        times = _jobs[job_id]["stage_times"]
        times[5] = now

        # Backfill any missing intermediate stage timestamps (2, 3, 4) so the
        # frontend always has enough data to compute per-stage durations.
        # We distribute the total elapsed time evenly across the 4 stages.
        if 1 in times:
            start_ts = datetime.fromisoformat(times[1])
            total_sec = (now_ts - start_ts).total_seconds()
            
            # Non-decreasing backfill: ensure each stage is at least the previous one
            prev_ts_iso = times[1]
            for stage_n in (2, 3, 4):
                if stage_n not in times:
                    fraction = (stage_n - 1) / 4
                    # Interpolated value relative to start
                    interp_sec = fraction * total_sec
                    interp_ts = start_ts + timedelta(seconds=interp_sec)
                    
                    # Clamp to ensure it's not earlier than the previous stage
                    prev_ts = datetime.fromisoformat(prev_ts_iso)
                    if interp_ts < prev_ts:
                        interp_ts = prev_ts
                    
                    times[stage_n] = interp_ts.isoformat()
                
                prev_ts_iso = times[stage_n]

    _update_job(
        job_id,
        stage=5,
        stage_label="done",
        status=final_status,
        exit_code=process.returncode,
        stdout=stdout,
        stderr=stderr,
        refactored_code=primary_code,
        validation_report=primary_report,
        per_file_results=per_file,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Meta"])
def health_check():
    return {
        "status":      "healthy",
        "service":     "AI Refactoring Pipeline",
        "active_jobs": len(_jobs),
    }


@app.post("/api/v1/refactor", tags=["Pipeline"], status_code=202)
async def submit_refactor_job(
    files:         List[UploadFile] = File(...),
    model:         str   = Form("gemma-3-1b-it"),
    batch_size:    int   = Form(3),
    delay:         float = Form(2.0),
    in_place:      bool  = Form(False),
    no_functional: bool  = Form(False),
):
    """
    Upload one or more Python files (or a .zip archive) and enqueue a
    refactoring job.

    Supported upload modes
    ----------------------
    - Single .py file
    - Multiple .py files   (``<input multiple>``)
    - Folder via browser   (``<input webkitdirectory>``) — browser sends each
      file individually with its relative path preserved in ``filename``
    - .zip archive         — extracted server-side; all .py files processed

    Returns a ``job_id`` for polling /status and /results.
    """
    job_id  = str(uuid.uuid4())
    job_dir = UPLOAD_DIR / job_id

    py_files = await _save_uploads(files, job_dir)

    if not py_files:
        raise HTTPException(
            status_code=400,
            detail="No .py files found in the upload. "
                   "Provide .py files directly or a .zip containing .py files.",
        )

    config = {
        "model":         model,
        "batch_size":    batch_size,
        "delay":         delay,
        "in_place":      in_place,
        "no_functional": no_functional,
    }

    filenames = [f.name for f in py_files]
    job = _new_job(job_id, filenames, config)
    _jobs[job_id] = job

    _executor.submit(_run_pipeline, job_id, py_files, config)

    return {
        "job_id":    job_id,
        "status":    "queued",
        "files":     filenames,
        "message":   f"Enqueued {len(py_files)} file(s). Poll /api/v1/status/{job_id}.",
        "ws_url":    f"ws://localhost:8000/api/v1/ws/{job_id}",
    }


@app.get("/api/v1/status/{job_id}", tags=["Pipeline"])
def get_job_status(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {
        "job_id":      job["job_id"],
        "filename":    job["filename"],
        "filenames":   job["filenames"],
        "status":      job["status"],
        "stage":       job["stage"],
        "stage_label": job["stage_label"],
        "stage_times": job.get("stage_times", {}),
        "created_at":  job["created_at"],
        "updated_at":  job["updated_at"],
        "error":       job.get("error"),
    }


@app.get("/api/v1/results/{job_id}", tags=["Pipeline"])
def get_job_results(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job["status"] in ("queued", "running"):
        raise HTTPException(status_code=425,
                            detail=f"Job is still {job['status']}. Try again later.")
    return {
        "job_id":             job["job_id"],
        "filename":           job["filename"],
        "filenames":          job["filenames"],
        "status":             job["status"],
        "exit_code":          job["exit_code"],
        "refactored_code":    job["refactored_code"],
        "validation_report":  job["validation_report"],
        "per_file_results":   job["per_file_results"],
        "stdout":             job["stdout"],
        "stderr":             job["stderr"],
    }


@app.get("/api/v1/jobs", tags=["Pipeline"])
def list_jobs():
    return [
        {
            "job_id":      j["job_id"],
            "filename":    j["filename"],
            "filenames":   j["filenames"],
            "status":      j["status"],
            "stage":       j["stage"],
            "stage_label": j["stage_label"],
            "created_at":  j["created_at"],
        }
        for j in reversed(list(_jobs.values()))
    ]


@app.post("/api/v1/jobs/{job_id}/cancel", tags=["Pipeline"])
def cancel_job(job_id: str):
    """Manually terminate a running job and its child processes."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    if job["status"] not in ("queued", "running"):
        return {"message": f"Job is already in status: {job['status']}"}

    _update_job(job_id, status="cancelled", stage_label="cancelled")

    with _proc_lock:
        process = _active_processes.pop(job_id, None)
        if process:
            _kill_process_tree(process)

    return {"message": "Job cancelled."}


@app.delete("/api/v1/jobs/cleanup", tags=["Meta"])
def cleanup_jobs():
    """Cancel all running jobs and clear the in-memory history."""
    global _jobs

    with _proc_lock:
        for jid, proc in list(_active_processes.items()):
            try:
                _kill_process_tree(proc)
            except Exception:
                pass
        _active_processes.clear()

    _jobs = {}
    return {"message": "All jobs terminated and history cleared."}


@app.websocket("/api/v1/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    await websocket.accept()
    if job_id not in _jobs:
        await websocket.send_json({"error": "Job not found."})
        await websocket.close()
        return

    with _ws_lock:
        _ws_connections.setdefault(job_id, []).append(websocket)

    await websocket.send_json(_jobs[job_id])

    try:
        while True:
            job = _jobs.get(job_id, {})
            if job.get("status") in ("completed", "failed", "cancelled"):
                await asyncio.sleep(0.5)
                break
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass
    finally:
        with _ws_lock:
            clients = _ws_connections.get(job_id, [])
            if websocket in clients:
                clients.remove(websocket)


# ─────────────────────────────────────────────────────────────────────────────
# Dev entrypoint
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
