# Failure & Mitigation Strategies — AI Refactoring Pipeline

> Updated to reflect the full system state including the REST API layer, async job queue, functional validator, and real-world failures observed during integration testing.

---

## 1. Pipeline Failures

| # | Failure | Stage | Symptom | Root Cause | Impact |
|---|---------|-------|---------|------------|--------|
| 1.1 | **Top-Level Code Omission** | cAST (S1) | `.refactored.py` identical to original; 0 prompts generated | `cAST` only targets `ast.FunctionDef` / `ast.ClassDef`. Files with only top-level script logic (loops, assignments) produce 0 chunks | Critical script logic left unrefactored |
| 1.2 | **Nested Chunk Duplication** | LLM Agent (S3) | Duplicated code blocks in output; `f()` appears both inside `solve()` and as a standalone block | Nested functions extracted as separate chunks; outer replacement overwrites the already-refactored inner chunk causing overlap | Syntax errors, redundant code, broken logic |
| 1.3 | **Loss of Global Architectural Context** | LLM Agent (S3) | LLM breaks cross-file dependencies; renames variables used elsewhere | Chunks passed to LLM with only local source — no surrounding file structure visible | Violation of SOLID/DRY principles; potential breaking changes |
| 1.4 | **Unicode Encode Error** | Orchestrator | `UnicodeEncodeError: 'charmap' codec` crashes the subprocess | Windows default console encoding `cp1252` cannot represent box-drawing characters (`━`, `│`) printed in the summary table | Job fails before pipeline starts |
| 1.5 | **Functional Validation ImportError** | Validator (S4) | `Could not import original: ImportError: No module named 'X'` | Functional validator dynamically imports the uploaded file; project-local dependencies (e.g., `from core import …`) are absent when only a single file is uploaded | Functional check marked as failed for valid code |
| 1.6 | **LLM Linting Violations** | Validator (S4) | E302/E303 blank-line errors, E501 line-too-long in refactored output | LLM generates slightly malformed spacing and occasional long lines; model has no PEP8 enforcement | Validation marked `warning`; triggers automatic retry pass |
| 1.7 | **API Timeout on Large Files** | API Server | Frontend request hangs; connection drops after ~30s | Synchronous `subprocess.run()` blocked the FastAPI event loop for the full pipeline duration | Job lost; no status visible to user |

---

## 2. Mitigation Strategies

| # | Failure Addressed | Mitigation | Status |
|---|-------------------|------------|--------|
| 2.1 | 1.1 Top-Level Code Omission | Extend `cAST` to detect "Module-Level" segments as a fallback chunk type, wrapping loose top-level code for refactoring | 🗓️ Planned |
| 2.2 | 1.2 Nested Chunk Duplication | **Scope-Aware Filter** in LLM Agent: before extracting chunks, build a parent-child map from the AST; exclude any node whose parent is also being extracted | ✅ Implemented |
| 2.3 | 1.3 Architectural Context Loss | **Architecture-Aware Prompts**: inject the full file's module-level docstring, imports, and class signatures into every chunk prompt as context | ✅ Implemented |
| 2.4 | 1.4 Unicode Encode Error | Force UTF-8 on `sys.stdout`/`sys.stderr` via `io.TextIOWrapper` at process start; pass `PYTHONUTF8=1` env var to all subprocesses | ✅ Fixed |
| 2.5 | 1.5 Functional ImportError | Detect `ImportError`/`ModuleNotFoundError` in `run_validation.py` and return `(True, "Skipped — unresolvable import …")` instead of failing; expose `--no-functional` flag for files with known external deps | ✅ Fixed |
| 2.6 | 1.6 LLM Linting Violations | Automatic retry pass: inject flake8 error report back into the LLM prompt with `--fix-linting` instructions; validator re-runs on retry output | ✅ Implemented (retry loop) |
| 2.7 | 1.7 API Timeout | Run pipeline in background `ThreadPoolExecutor` (4 workers); return `202 Accepted` with `job_id` immediately; expose `/status`, `/results`, and WebSocket endpoints | ✅ Fixed |

---

## 3. Upload & Multi-File Failures

| # | Failure | Symptom | Root Cause | Mitigation | Status |
|---|---------|---------|------------|------------|--------|
| 3.1 | **Single-file context gap** | Functional tests always fail for files with project imports | Only one `.py` uploaded; dependencies missing | Folder upload mode (`webkitdirectory`), ZIP upload, `--no-functional` flag | ✅ Implemented |
| 3.2 | **ZIP path traversal** | Malicious ZIP extracts files outside job directory | `zipfile` follows `../` paths in member names | Filter members: skip any entry whose resolved path escapes `job_dir` | ✅ Implemented |
| 3.3 | **Empty upload** | API returns 500 on file-type mismatch | No `.py` files found after filtering non-Python uploads | Return `400 Bad Request` with explicit message: *"No .py files found in the upload"* | ✅ Implemented |

---

## 4. Continuous Improvement Roadmap

| Priority | Item | Notes |
|----------|------|-------|
| High | **Module-Level chunk support** in `cAST` | Unblocks refactoring of script files without functions |
| High | **Firebase Auth integration** | Protect API endpoints with Firebase ID token validation |
| Medium | **Semantic / AST-based diffing** | Verify logic equivalence beyond syntax (compare control-flow graphs) |
| Medium | **Streaming pipeline output** | Orchestrator emits machine-readable stage events to stdout; backend relays via WebSocket in real time instead of timed estimates |
| Low | **Celery + Redis job queue** | Replace `ThreadPoolExecutor` for horizontal scaling and persistent job history across restarts |
| Low | **Batch file download** | Allow users to download all refactored files as a `.zip` from the results panel |
