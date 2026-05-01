"""
backend/orchestrate.py
======================
Entry point for the end-to-end AI refactoring pipeline.

Stages
------
1. cAST          — parse source into structured chunks (JSON)
2. Prompt Builder — convert chunks into LLM prompts
3. LLM Agent     — call Gemini -> produce *.refactored.py
4. Validator     — check syntax, AST, lint, behavioral equivalence

Behaviour (v2)
--------------
* All files are always processed — validation failure NEVER stops the batch.
* A summary table is printed after the first pass.
* Files that fail validation are automatically retried once:
  - Stage 2 regenerates fresh prompts.
  - The full validation error report is injected into every prompt so the
    LLM can see exactly what went wrong and avoid repeating it.
  - Stage 3 re-runs with the enriched prompts.
  - Stage 4 re-validates the new output.
* A final summary table is printed after all retries.
* Use --no-retry to disable the retry pass.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# ── Force UTF-8 output on Windows (avoids cp1252 UnicodeEncodeError with
#    box-drawing / emoji characters in the summary table) ──────────────────────
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# ─────────────────────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FileResult:
    filename:        str
    original_path:   Path
    refactored_path: Optional[Path] = None

    stage1_ok: bool = False
    stage2_ok: bool = False
    stage3_ok: bool = False

    val_passed:    Optional[bool] = None   # None = not yet run / skipped
    val_severity:  str = "—"
    val_pass_rate: str = "—"
    val_error:     str = "—"

    retried:           bool = False
    retry_val_passed:  Optional[bool] = None
    retry_severity:    str = "—"
    retry_error:       str = "—"

    @property
    def final_status(self) -> str:
        if self.retried and self.retry_val_passed is not None:
            return "PASS" if self.retry_val_passed else "FAIL"
        if self.val_passed is None:
            return "SKIP"
        return "PASS" if self.val_passed else "FAIL"


# ─────────────────────────────────────────────────────────────────────────────
# Shell helper — never calls sys.exit, propagates termination
# ─────────────────────────────────────────────────────────────────────────────

import signal as _signal

_active_child: subprocess.Popen | None = None


def _sigterm_handler(signum, frame):
    """When orchestrate.py is killed, also kill the active child process."""
    if _active_child and _active_child.poll() is None:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(_active_child.pid)],
                capture_output=True,
            )
        else:
            _active_child.terminate()
    sys.exit(128 + signum)


# Register signal handlers for graceful teardown
_signal.signal(_signal.SIGINT, _sigterm_handler)
if sys.platform != "win32":
    _signal.signal(_signal.SIGTERM, _sigterm_handler)


def _run(command: str, env: dict | None = None, description: str = "") -> int:
    """Run *command* and return its exit code. Does NOT abort on failure."""
    global _active_child
    print(f"\n--- Running: {description} ---")
    print(f"Command: {command}")
    _active_child = subprocess.Popen(command, env=env, shell=True)
    rc = _active_child.wait()
    _active_child = None
    if rc == 0:
        print(f"--- {description} completed successfully ---\n")
    else:
        print(f"--- {description} FAILED (exit {rc}) ---\n")
    return rc


# ─────────────────────────────────────────────────────────────────────────────
# Validation report helpers
# ─────────────────────────────────────────────────────────────────────────────

def _read_val_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _build_error_context(val_json: dict, txt_report: Path) -> str:
    """
    Construct the error preamble that is prepended to every retry prompt.
    Combines structured JSON data with the full text report so the LLM
    has maximum context about what went wrong.
    """
    severity = val_json.get("severity", "unknown").upper()
    checks   = val_json.get("checks", {})
    fd       = val_json.get("functional_detail", {})

    failed_lines: list[str] = []
    for name, info in checks.items():
        if isinstance(info, dict) and not info.get("passed", True):
            failed_lines.append(f"  - [{name}] {info.get('message', '')}")
        elif isinstance(info, list) and len(info) >= 2 and not info[0]:
            failed_lines.append(f"  - [{name}] {info[1]}")
    for pf in fd.get("property_failures", []):
        failed_lines.append(
            f"  - [property:{pf.get('property','')}] "
            f"{pf.get('function','')} — {pf.get('message','')}"
        )

    failed_block = "\n".join(failed_lines) or "  (see full report below)"

    full_report_text = ""
    try:
        full_report_text = txt_report.read_text(encoding="utf-8")
    except Exception:
        pass

    return (
        "=================================================================\n"
        "  WARNING: PREVIOUS REFACTORING ATTEMPT FAILED VALIDATION\n"
        "=================================================================\n\n"
        f"Severity : {severity}\n\n"
        "Failed checks:\n"
        f"{failed_block}\n\n"
        "Full validation report:\n"
        "-----------------------------------------------------------------\n"
        f"{full_report_text}\n"
        "-----------------------------------------------------------------\n\n"
        "YOU MUST FIX ALL OF THE ABOVE ERRORS IN THIS RETRY ATTEMPT.\n"
        "Key rules:\n"
        "  1. Correct Python indentation — no unexpected indents\n"
        "  2. Preserve ALL original logic exactly\n"
        "  3. No new syntax errors of any kind\n"
        "  4. Match original function/method signatures precisely\n"
        "  5. Do not add imports that were not in the original\n\n"
        "=================================================================\n"
        "ORIGINAL REFACTORING TASK (with above constraint added):\n"
        "=================================================================\n\n"
    )


def _inject_context(prompts_file: Path, prefix: str) -> None:
    """Prepend *prefix* to every prompt in *prompts_file* (in-place)."""
    data = json.loads(prompts_file.read_text(encoding="utf-8"))
    for p in data.get("prompts", []):
        p["prompt"] = prefix + p.get("prompt", "")
    prompts_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  [retry] Validation context injected into {prompts_file.name}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Summary table
# ─────────────────────────────────────────────────────────────────────────────

def _print_table(results: list[FileResult], title: str) -> None:
    W_FILE  = max(22, max(len(r.filename) for r in results) + 2)
    W_VAL   = 12
    W_SEV   = 9
    W_RATE  = 9
    W_RETRY = 12
    W_ERR   = 40

    def _hline(left, mid, right, fill="─"):
        parts = [fill*(W_FILE+2), fill*(W_VAL+2), fill*(W_SEV+2),
                 fill*(W_RATE+2), fill*(W_RETRY+2), fill*(W_ERR+2)]
        return left + mid.join(parts) + right

    def _row(f, v, s, r, re, e):
        return (
            f"│ {f:<{W_FILE}} │ {v:<{W_VAL}} │ {s:<{W_SEV}} │"
            f" {r:<{W_RATE}} │ {re:<{W_RETRY}} │ {e:<{W_ERR}} │"
        )

    STATUS_ICON = {"PASS": "✓ PASS", "FAIL": "✗ FAIL", "SKIP": "— SKIP"}

    print(f"\n{'━'*66}")
    print(f"  {title}")
    print(f"{'━'*66}")
    print(_hline("┌", "┬", "┐"))
    print(_row("File", "Validation", "Severity", "PassRate", "After Retry", "Error / Notes"))
    print(_hline("├", "┼", "┤", "─"))

    for r in results:
        v_str  = STATUS_ICON.get(
            "PASS" if r.val_passed else ("FAIL" if r.val_passed is False else "SKIP"), "—"
        )
        re_str = "—"
        if r.retried:
            re_str = STATUS_ICON.get(
                "PASS" if r.retry_val_passed else ("FAIL" if r.retry_val_passed is False else "SKIP"), "—"
            )
        err_str = r.val_error
        if r.retried and r.retry_error and r.retry_error != "—":
            err_str = r.retry_error
        err_str = (err_str[:W_ERR-1] + "…") if len(err_str) > W_ERR else err_str

        print(_row(
            r.filename,
            v_str,
            r.val_severity,
            r.val_pass_rate,
            re_str,
            err_str,
        ))

    print(_hline("└", "┴", "┘"))

    passed  = sum(1 for r in results if r.final_status == "PASS")
    failed  = sum(1 for r in results if r.final_status == "FAIL")
    skipped = sum(1 for r in results if r.final_status == "SKIP")
    retried = sum(1 for r in results if r.retried)
    recovered = sum(1 for r in results if r.retried and r.retry_val_passed)

    print(
        f"\n  Total: {len(results)}"
        f"  │  ✓ Passed: {passed}"
        f"  │  ✗ Failed: {failed}"
        f"  │  — Skipped: {skipped}"
        f"  │  ↺ Retried: {retried}"
        f"  │  ↑ Recovered: {recovered}\n"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Stage runners
# ─────────────────────────────────────────────────────────────────────────────

def _stages_1_to_3(
    input_path:   Path,
    output_dir:   Path,
    pipeline_dir: Path,
    chunks_file:  Path,
    prompts_file: Path,
    model: str, batch_size: int, delay: float, in_place: bool,
    tag: str = "",
) -> tuple[bool, bool, bool]:
    """Run cAST → Prompt Builder → LLM Agent. Returns (s1_ok, s2_ok, s3_ok)."""
    fn  = input_path.name
    sfx = f" [{tag}]" if tag else ""

    cast_env = os.environ.copy()
    cast_env["PYTHONPATH"] = str(pipeline_dir / "cast")
    if _run(f'python -m cast.pipeline "{input_path}" "{chunks_file}" -v',
            env=cast_env, description=f"Stage 1: cAST{sfx} - {fn}") != 0:
        return False, False, False

    pb_env = os.environ.copy()
    pb_env["PYTHONPATH"] = str(pipeline_dir / "prompt_builder")
    if _run(
        f'python -m prompt_builder.build_prompts '
        f'-i "{chunks_file}" -o "{prompts_file}" --batch-size {batch_size} -v',
        env=pb_env, description=f"Stage 2: Prompt Builder{sfx} - {fn}",
    ) != 0:
        return True, False, False

    la_env = os.environ.copy()
    la_env["PYTHONPATH"] = str(pipeline_dir / "llm_agent")
    la_cmd = (
        f'python -m llm_agent.run_agent --input "{prompts_file}" '
        f'--model {model} --output-dir "{output_dir}" --delay {delay}'
    )
    if in_place:
        la_cmd += " --in-place"
    rc3 = _run(la_cmd, env=la_env, description=f"Stage 3: LLM Agent{sfx} - {fn}")
    return True, True, (rc3 == 0)


def _stage_4(
    input_path:    Path,
    refactored:    Path,
    output_dir:    Path,
    pipeline_dir:  Path,
    stem:          str,
    tag:           str = "",
    no_functional: bool = False,
) -> dict:
    """Run Validator. Returns outcome dict."""
    fn  = input_path.name
    sfx = f" [{tag}]" if tag else ""

    r_txt  = output_dir / f"{stem}_validation_report.txt"
    r_json = output_dir / f"{stem}_validation_report.json"
    script = pipeline_dir / "validator" / "run_validation.py"

    no_func_flag = "--no-functional" if no_functional else ""
    rc = _run(
        f'python "{script}" file '
        f'--original "{input_path}" --refactored "{refactored}" '
        f'--report "{r_txt}" --json-report "{r_json}" {no_func_flag}'.strip(),
        description=f"Stage 4: Validator{sfx} - {fn}",
    )

    jd      = _read_val_json(r_json)
    passed  = (rc == 0)
    sev     = jd.get("severity", "error" if not passed else "pass")
    rate    = jd.get("pass_rate")
    rate_s  = f"{rate:.0%}" if rate is not None else "—"

    err = "—"
    for name, info in jd.get("checks", {}).items():
        failed = False
        msg    = ""
        if isinstance(info, dict):
            failed, msg = not info.get("passed", True), info.get("message", "")
        elif isinstance(info, list) and len(info) >= 2:
            failed, msg = not info[0], info[1]
        if failed:
            err = f"[{name}] " + (msg[:55] + "…" if len(msg) > 55 else msg)
            break

    return {
        "passed": passed, "severity": sev,
        "pass_rate": rate_s, "error": err,
        "report_txt": r_txt, "report_json": r_json, "val_data": jd,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="AI Code Refactoring Pipeline")
    parser.add_argument("inputs", nargs="+")
    parser.add_argument("--model",          default="gemma-3-1b")
    parser.add_argument("--in-place",       action="store_true")
    parser.add_argument("--delay",          type=float, default=2.0)
    parser.add_argument("--batch-size",     type=int,   default=3)
    parser.add_argument("--no-retry",       action="store_true",
                        help="Skip the automatic retry pass for failed files")
    parser.add_argument("--no-functional",  action="store_true",
                        help="Skip functional/behavioral validation in Stage 4")
    args = parser.parse_args()

    # Collect source files
    source_files: list[Path] = []
    for item in args.inputs:
        p = Path(item).resolve()
        if not p.exists():
            p = (Path(__file__).parent / "input" / item).resolve()
        if not p.exists():
            print(f"[WARN] Not found, skipping: {item}")
            continue
        source_files.extend(sorted(p.glob("*.py")) if p.is_dir() else [p])

    if not source_files:
        print("[ERROR] No valid source files found.")
        sys.exit(1)

    root_dir     = Path(__file__).parent.resolve()
    pipeline_dir = root_dir / "pipeline"
    output_dir   = root_dir / "output"
    output_dir.mkdir(exist_ok=True)

    total   = len(source_files)
    results: list[FileResult] = []

    # ══════════════════════════════════════════════════════════════════════
    #  FIRST PASS  —  all files, no stopping
    # ══════════════════════════════════════════════════════════════════════

    for idx, input_path in enumerate(source_files, start=1):
        stem     = input_path.stem
        filename = input_path.name

        print(f"\n{'━'*66}")
        print(f"  FIRST PASS  [{idx}/{total}]  {filename}")
        print(f"{'━'*66}")

        chunks_file  = output_dir / f"{stem}_chunks.json"
        prompts_file = output_dir / f"{stem}_prompts.json"
        refactored   = output_dir / f"{stem}.refactored.py"

        r = FileResult(filename=filename, original_path=input_path,
                       refactored_path=refactored)

        s1, s2, s3 = _stages_1_to_3(
            input_path, output_dir, pipeline_dir,
            chunks_file, prompts_file,
            args.model, args.batch_size, args.delay, args.in_place,
        )
        r.stage1_ok, r.stage2_ok, r.stage3_ok = s1, s2, s3

        if s3 and refactored.exists():
            v = _stage_4(input_path, refactored, output_dir, pipeline_dir, stem,
                         no_functional=args.no_functional)
            r.val_passed   = v["passed"]
            r.val_severity = v["severity"]
            r.val_pass_rate = v["pass_rate"]
            r.val_error    = v["error"]
        else:
            r.val_error = (
                "Stage 1 failed" if not s1 else
                "Stage 2 failed" if not s2 else
                "Stage 3 failed" if not s3 else
                "No refactored file produced"
            )

        results.append(r)

    _print_table(results, "FIRST PASS RESULTS")

    # ══════════════════════════════════════════════════════════════════════
    #  RETRY PASS  —  failed files re-sent with validation context
    # ══════════════════════════════════════════════════════════════════════

    to_retry = [r for r in results if r.val_passed is False]

    if args.no_retry:
        print("  Retry pass skipped (--no-retry).\n")
    elif not to_retry:
        print("  ✓ All files passed — no retries needed.\n")
    else:
        print(f"\n{'━'*66}")
        print(f"  RETRY PASS  —  {len(to_retry)} file(s) failed, re-sending to LLM")
        print(f"  The full validation report will be injected into each prompt.")
        print(f"{'━'*66}")

        for idx, r in enumerate(to_retry, start=1):
            input_path   = r.original_path
            stem         = input_path.stem
            filename     = r.filename
            chunks_file  = output_dir / f"{stem}_chunks.json"
            prompts_file = output_dir / f"{stem}_prompts.json"
            refactored   = output_dir / f"{stem}.refactored.py"
            report_txt   = output_dir / f"{stem}_validation_report.txt"
            report_json  = output_dir / f"{stem}_validation_report.json"

            print(f"\n{'━'*66}")
            print(f"  RETRY [{idx}/{len(to_retry)}]  {filename}")
            print(f"{'━'*66}")

            r.retried = True

            # Stage 2: regenerate prompts (chunks from first pass are reused)
            pb_env = os.environ.copy()
            pb_env["PYTHONPATH"] = str(pipeline_dir / "prompt_builder")
            rc2 = _run(
                f'python -m prompt_builder.build_prompts '
                f'-i "{chunks_file}" -o "{prompts_file}" '
                f'--batch-size {args.batch_size} -v',
                env=pb_env,
                description=f"Stage 2: Prompt Builder [RETRY] - {filename}",
            )
            if rc2 != 0:
                r.retry_val_passed = False
                r.retry_severity   = "error"
                r.retry_error      = "Stage 2 failed on retry"
                continue

            # Inject the full validation error report into every prompt
            val_data = _read_val_json(report_json)
            _inject_context(prompts_file, _build_error_context(val_data, report_txt))

            # Stage 3: LLM with enriched prompts
            la_env = os.environ.copy()
            la_env["PYTHONPATH"] = str(pipeline_dir / "llm_agent")
            la_cmd = (
                f'python -m llm_agent.run_agent --input "{prompts_file}" '
                f'--model {args.model} --output-dir "{output_dir}" '
                f'--delay {args.delay}'
            )
            if args.in_place:
                la_cmd += " --in-place"
            rc3 = _run(la_cmd, env=la_env,
                       description=f"Stage 3: LLM Agent [RETRY] - {filename}")

            if rc3 != 0 or not refactored.exists():
                r.retry_val_passed = False
                r.retry_severity   = "error"
                r.retry_error      = "Stage 3 failed on retry"
                continue

            # Stage 4: re-validate
            v = _stage_4(
                input_path, refactored, output_dir, pipeline_dir, stem,
                tag="RETRY", no_functional=args.no_functional,
            )
            r.retry_val_passed = v["passed"]
            r.retry_severity   = v["severity"]
            r.retry_error      = v["error"]

        _print_table(results, "FINAL RESULTS  (after retries)")

    # ── Exit code ─────────────────────────────────────────────────────────
    sys.exit(0 if all(r.final_status == "PASS" for r in results) else 1)


if __name__ == "__main__":
    main()