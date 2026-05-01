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
import subprocess
import sys
import threading
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
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


# ─────────────────────────────────────────────────────────────────────────────
# File helpers
# ─────────────────────────────────────────────────────────────────────────────

def _collect_py_files(job_dir: Path) -> list[Path]:
    """Return all .py files recursively inside *job_dir*."""
    return sorted(job_dir.rglob("*.py"))


async def _save_uploads(
    files: List[UploadFile],
    job_dir: Path,
) -> list[Path]:
    """
    Save every uploaded file into *job_dir*.
    Handles three cases:
    - .zip   → extract all .py files
    - .py    → save directly
    - other  → ignored with a warning
    Returns the list of saved .py paths.
    """
    job_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []

    for uf in files:
        contents = await uf.read()
        name = uf.filename or "upload"

        if name.endswith(".zip"):
            # Extract zip and collect .py files
            try:
                with zipfile.ZipFile(io.BytesIO(contents)) as zf:
                    for member in zf.namelist():
                        if member.endswith(".py") and not member.startswith("__"):
                            dest = job_dir / Path(member).name
                            dest.write_bytes(zf.read(member))
                            saved.append(dest)
            except zipfile.BadZipFile:
                pass  # skip malformed zips
        elif name.endswith(".py"):
            # Preserve relative path for folder uploads
            # (browser sends filename as "folder/sub/file.py")
            rel = Path(name)
            dest = job_dir / rel.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(contents)
            saved.append(dest)
        # Other types silently ignored

    return saved


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline runner (background thread)
# ─────────────────────────────────────────────────────────────────────────────

def _advance_stage(job_id: str, stage: int) -> None:
    _update_job(job_id, stage=stage, stage_label=STAGE_LABELS[stage], status="running")


def _run_pipeline(job_id: str, py_files: list[Path], config: dict) -> None:
    """Run orchestrate.py against one or more .py files."""
    _advance_stage(job_id, 1)

    cmd = [
        sys.executable,
        str(BASE_DIR / "orchestrate.py"),
        *[str(f) for f in py_files],
        "--model",      config["model"],
        "--batch-size", str(config["batch_size"]),
        "--delay",      str(config["delay"]),
    ]
    if config.get("in_place"):
        cmd.append("--in-place")
    if config.get("no_functional"):
        cmd.append("--no-functional")

    # Timed stage advancement (best-effort estimate while subprocess runs)
    t2 = threading.Timer(8.0,  _advance_stage, args=(job_id, 2))
    t3 = threading.Timer(16.0, _advance_stage, args=(job_id, 3))
    t4 = threading.Timer(24.0, _advance_stage, args=(job_id, 4))
    t2.start(); t3.start(); t4.start()

    try:
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",    # decode stdout/stderr as UTF-8, not cp1252
            errors="replace",    # replace undecodable bytes instead of crashing
            timeout=600,
            cwd=str(BASE_DIR),
            env=env,
        )
    except subprocess.TimeoutExpired:
        for t in (t2, t3, t4): t.cancel()
        _update_job(job_id, stage=0, stage_label="idle", status="failed",
                    error="Pipeline timed out after 10 minutes.")
        return
    except Exception as exc:
        for t in (t2, t3, t4): t.cancel()
        _update_job(job_id, stage=0, stage_label="idle", status="failed",
                    error=str(exc))
        return

    for t in (t2, t3, t4): t.cancel()

    # Collect per-file artefacts
    per_file: list[dict] = []
    primary_code: str | None = None
    primary_report: dict = {}

    for py_path in py_files:
        stem = py_path.stem
        refactored_file = OUTPUT_DIR / f"{stem}.refactored.py"
        report_json     = OUTPUT_DIR / f"{stem}_validation_report.json"

        code = refactored_file.read_text(encoding="utf-8") if refactored_file.exists() else None
        report: dict = {}
        if report_json.exists():
            try:
                report = json.loads(report_json.read_text(encoding="utf-8"))
            except Exception:
                pass

        entry = {
            "filename":          py_path.name,
            "refactored_code":   code,
            "validation_report": report,
        }
        per_file.append(entry)

        # Use first file as the "primary" result for backwards compat
        if primary_code is None and code:
            primary_code = code
            primary_report = report

    final_status = "completed" if process.returncode == 0 else "failed"

    _update_job(
        job_id,
        stage=5,
        stage_label="done",
        status=final_status,
        exit_code=process.returncode,
        stdout=process.stdout,
        stderr=process.stderr,
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
    model:         str   = Form("gemini-2.5-flash"),
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
            if job.get("status") in ("completed", "failed"):
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
