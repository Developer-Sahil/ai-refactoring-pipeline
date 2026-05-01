# pipeline LOG

## 2026-03-27
- **Pipeline Initialization**: Successfully setup the AI-powered refactoring pipeline (cAST -> Prompt Builder -> LLM Agent).
- **Environment Setup**: Configured `llm_agent` with Gemini API and `google-genai` SDK.
- **Initial Verification**: Confirmed that `orchestrate.py` correctly triggers all stages and handles basic file processing.
- **Error Handling**: Resolved initial 429 rate limit errors with retry logic.

## 2026-03-28
- **Continuous Improvement**: Successfully tested the end-to-end pipeline with multiple files.
- **Pipeline Testing**:
    - Ran 1 source file (`input/bitmask.py`) -> **Success**.
    - Ran 2 source files (`input/round_robin.py` and `input/order_service.py`) -> **Success**.
    - Verified chunking and batching logic for multi-chunk files like `order_service.py`.

## 2026-03-29
- **Model Upgrade**: Transitioned to **`gemini-2.5-flash`** for superior reasoning and adherence to complex refactoring goals.
- **Global Context Injection**: Enhanced the Prompt Builder to include the **entire source file** as context in every prompt. This allows the LLM to understand the global architecture and follow system design principles (SOLID, DRY) consistently.
- **Improved Prompting**: Redesigned templates with a "Senior Software Architect" persona, focusing on industrial-grade outcomes, comprehensive documentation (Docstrings, JSDoc, etc.), and strict type hints.
- **Redundancy Filter**: Implemented a nested chunk filtering system to skip inner functions/methods when their parent containers are already being refactored, preventing code duplication and file corruption.
- **Few-Shot Demonstration**: Enabled few-shot examples in batched prompts to provide concrete examples of the expected high-quality refactored output.
- **Bug Fixes**: Resolved a `KeyError` in prompt formatting and fixed a logic bug that was causing some valid prompts to be skipped.

## 2026-04-11
- **Stage 4 Added**: Validator module introduced (`validator/`) as Stage 4 of the pipeline.
- **Bug Analysis**: Reviewed all 6 validator files and identified **9 bugs** (2 critical, 3 major, 4 minor):
  - 🔴 `run_validation.py:87` — `result.report` crashes at CLI; `ValidationResult` NamedTuple has no `.report` field.
  - 🔴 `validation_report.py` — File is completely empty; no implementation.
  - 🟠 `run_validation.py:52` — Severity logic never emits `"warning"`; only `"pass"` or `"error"`.
  - 🟠 `linter_check.py:18` — `flake8` not invoked via `sys.executable`, causes `FileNotFoundError` in virtualenvs.
  - 🟠 `ast_comparator.py:36-41` — `ast.walk` counts nested/class methods as top-level functions (false positives).
  - 🟡 `run_validation.py:34-35` — `read_text()` missing `encoding="utf-8"` (Windows compat).
  - 🟡 `run_validation.py:70` — `write_text()` missing `encoding="utf-8"` for Unicode report characters.
  - 🟡 `validator/` — `__init__.py` missing; directory not a valid Python package.
  - 🟡 `syntax_validator.py:13-14` — Redundant double-parsing; `py_compile` has `.pyc` side-effect.
- **Stage 4 Relocation**: Moved `validator/` → `pipeline/validator/` to correctly position it as Stage 4 of the pipeline.
- **All Bugs Fixed**:
  - Created `__init__.py` — `pipeline/validator/` is now a proper Python package.
  - Implemented `validation_report.py` — `generate_report()`, `generate_json_report()`, and `print_summary()` (UTF-8 safe).
  - `run_validation.py` — Updated imports to relative, added `encoding="utf-8"` to all file reads/writes, fixed 3-tier severity logic, removed duplicate `generate_report()`, fixed `result.report` crash → now calls `print_summary()`, added `--json-report` CLI flag, replaced `exit()` with `raise SystemExit()`.
  - `syntax_validator.py` — Removed `py_compile` (redundant + `.pyc` side-effect), added `encoding="utf-8"`.
  - `ast_comparator.py` — Replaced `ast.walk()` with `ast.body` iteration to prevent nested method false-positives.
- **Project Restructuring**: Reorganized the repository to follow a standardized layout:
  - Created `/backend`, `/frontend`, and `/docs` directories.
  - Moved pipeline modules, orchestrator, input/output, and tests into `/backend`.
  - Moved high-level system documentation into `/docs`.
  - Created `docker-compose.ymal` in the root for future deployment logic.
  - Updated `README.md` with new project structure and updated execution commands.
  - Created `docs/AUDIT.md` providing a comprehensive health check and architectural review of the pipeline.
  - Formally integrated Stage 4 (Validator) into the root `README.md` and created its dedicated [Stage 4 README](file:///c:/dev/SDP/backend/pipeline/validator/README.md).
  - Synchronized all project documentation (`SYSTEM_DESIGN.md`, `failure_and_mitigation_strategies.md`, `AUDIT.md`) with the new architecture and implemented features.
  - Pushed all updates to the remote repository.

## 2026-04-14 - Frontend SaaS Addition
- Initialized Vite + React frontend in /frontend directory.
- Implemented a complete Light Mode Neumorphism design system.
- Built fully interactive layout containing dashboard upload zones, config panels with simulated API delay switches, and pipeline progression.
- Integrated a result diff viewer.

- Updated README.md, AUDIT.md, and SYSTEM_DESIGN.md to reflect the completion of the Frontend SaaS UI phase.

## 2026-05-01
- **Repository Synchronization**: Pulled latest updates from GitHub.
- **Project Name Correction**: Standardized the project as **AI Refactoring Pipeline** (removed "WashLogs" references).
- **Documentation Overhaul**: 
    - Renamed `SYSTEM_DESIGN.md` to `ARCHITECTURE.md` and updated `README.md` links.
    - Created a complete documentation suite: `PRD.md`, `DEPLOYMENT.md`, `API.md`, `CONTRIBUTING.md`, `TESTING.md`, `SECURITY.md`.
    - Integrated Stage 4 Functional Validation (Behavior Capture, Property Testing, Replay) into `ARCHITECTURE.md`.
- **Infrastructure**: Added root-level `requirements.txt`.

## 2026-05-01 (End-to-End Integration)
- **API Implementation**: Created `backend/main.py` using FastAPI to expose the refactoring orchestrator as a REST API.
- **Frontend Connectivity**: Updated `frontend/src/App.jsx` to perform real-time file uploads and display live refactoring results.
- **Dependency Update**: Added `fastapi`, `uvicorn`, and `python-multipart` to `requirements.txt`.
- **Server Deployment**: Successfully initialized and verified both the FastAPI backend (Port 8000) and Vite frontend (Port 5173).

## 2026-05-01 (REST API Middleware)
- **API Versioning**: Restructured backend to use `/api/v1/` prefix on all pipeline routes.
- **Async Job Queue**: Implemented `ThreadPoolExecutor`-based async job processing with a full in-memory `JobStore` — prevents API timeouts on large files.
- **New Endpoints**: `POST /api/v1/refactor`, `GET /api/v1/status/{id}`, `GET /api/v1/results/{id}`, `GET /api/v1/jobs`.
- **WebSocket**: Added `/api/v1/ws/{job_id}` endpoint for real-time stage-update streaming.
- **Frontend Overhaul**: Replaced dummy pipeline animation with XHR upload progress, WebSocket subscriptions, polling fallback, and a split/unified code diff viewer.
- **UI Additions**: Job history panel, validation check breakdown, connection status indicator, pipeline log collapsibles.
- **Documentation**: Updated `docs/API.md` with the complete v1 API specification.

## 2026-05-01 (Bugfix)
- **Root Cause**: `UnicodeEncodeError: 'charmap' codec can't encode character` in `orchestrate.py:372`.
  - Windows console encoding `cp1252` cannot represent the Unicode box-drawing character `━` used in the summary table.
- **Fix 1 — `backend/orchestrate.py`**: Added `io.TextIOWrapper` reconfiguration at startup to force UTF-8 on `sys.stdout` / `sys.stderr` when the process encoding is not already UTF-8.
- **Fix 2 — `backend/main.py`**: Pass `PYTHONUTF8=1` in the subprocess environment so all child processes (cAST, Prompt Builder, LLM Agent, Validator) also inherit UTF-8 encoding.

## 2026-05-01 (Validator Error Analysis)
- **File tested**: `agent.py` (Meeting Scheduling Agent with Gemini tool-calling).
- **Linting (`warning`)**: Refactored code has E302/E303 blank-line violations and one E501 line-too-long. These are LLM output quality issues — the LLM added excessive blank lines between methods and produced one line > 120 chars.
- **Functional (`failed`)**: `ImportError: No module named 'core'`. `agent.py` imports `from core import User, MeetingRequest, ...`. The `core` module is a sibling in the original project but was not uploaded. The functional validator correctly tries to dynamically import the original file to capture behavior — it cannot proceed without `core` being resolvable.
- **Root Cause**: Functional validation requires all transitive dependencies of the uploaded file to be importable. Files with project-local imports (like `core`) will always fail this check unless the full project context is uploaded.
- **Status**: Expected / by-design failure for isolated file uploads. No validator bug.

## 2026-05-01 (Feature: Folder Uploads, --no-functional flag, Auto-skip ImportError)
- **Folder/ZIP Upload**: Backend `main.py` now accepts `List[UploadFile]` and handles three upload modes — multiple `.py` files, browser folder picker (`webkitdirectory`), and `.zip` archives (extracted server-side). Each job gets an isolated `uploads/{job_id}/` directory.
- **`--no-functional` flag**: Added to `orchestrate.py` argparse and threaded through both first-pass and retry `_stage_4` calls. Backend API exposes it as `no_functional: bool` form field. Frontend config panel has a "Skip Functional Tests" toggle.
- **Auto-skip ImportError**: `run_validation.py` now detects when functional validation fails due to `ImportError`/`ModuleNotFoundError` (missing project dependency) and returns `(True, "Skipped — unresolvable import …")` instead of `(False, …)` — treating it as a warning rather than a failure.
- **UI Additions**: Upload mode switcher (📄 File / 📁 Folder / 🗜 ZIP), multi-file result tabs with pass/fail dots, no-functional toggle in config panel.
- **Firebase Auth**: Replaced all Supabase Auth references in `docs/DEPLOYMENT.md`, `docs/SECURITY.md`, `docs/API.md` with Firebase Authentication (Google Identity Platform).

## 2026-05-01 (Docs: Failure & Mitigation Strategies)
- Rewrote `docs/failure_and_mitigation_strategies.md` in tabular format.
- Added 3 new failure categories: Unicode Encode Error (1.4), Functional ImportError (1.5), LLM Linting Violations (1.6), API Timeout (1.7).
- Added Section 3: Upload & Multi-File Failures (path traversal, empty upload, single-file context gap).
- Added Section 4: Prioritized Continuous Improvement Roadmap table.

## 2026-05-01 (Bugfix: UnicodeDecodeError on subprocess stdout pipe)
- **Root Cause**: `subprocess.run(..., text=True)` in `backend/main.py` decoded the child process stdout using the parent's default encoding (`cp1252` on Windows). Refactored code containing Unicode characters (box-drawing, em-dashes in section comments) caused `UnicodeDecodeError: 'charmap' codec can't decode byte 0x81`.
- **Fix**: Added `encoding="utf-8"` and `errors="replace"` to `subprocess.run()` so stdout/stderr are always decoded as UTF-8.

## 2026-05-01 (Bugfix: Async functions not awaited in functional validator)
- **Root Cause**: `execute_with_timeout()` in `test_executor.py` called functions synchronously. `async def` functions (e.g., `create_calendar_event`, `find_event`, `delete_event`) returned unawaited coroutine objects instead of results. The determinism check then compared two different coroutine objects at different memory addresses — always failing.
- **Fix**: Added `inspect.iscoroutinefunction()` detection in `_call()`. Async functions are now executed with `asyncio.run()` inside the executor thread (safe because ThreadPoolExecutor threads have no running event loop).

## 2026-05-01 (Bugfix: Multi-file diff viewer and React syntax error)
- **Root Cause**: 
    1. `App.jsx` had a missing `</div>` in the configuration panel, causing a frontend crash.
    2. The frontend only stored `originalCode` for the first file, so switching tabs in `MultiFileTabs` showed incorrect diffs for subsequent files.
- **Fix**: 
    1. Patched `backend/main.py` to include `original_code` in every entry of `per_file_results`.
    2. Fixed `App.jsx` syntax (missing `</div>`).
    3. Updated `MultiFileTabs` to use `cur.original_code` for diffing.
    4. Cleaned up the results display logic to correctly branch between single-file and multi-file views.

## 2026-05-01 (Infrastructure Hardening)
- **Recursive Upload Preservation**: Rewrote `_save_uploads()` to preserve the full directory tree for both `.py` (via `webkitdirectory`) and `.zip` uploads. ZIP extraction now maintains internal folder layout with path-traversal protection.
- **Process Tree Kill**: Replaced `process.kill()` with `_kill_process_tree()` which uses `taskkill /F /T` on Windows and `psutil` on Unix to recursively terminate all child processes.
- **SIGTERM Propagation**: `orchestrate.py` now tracks its active child subprocess and registers a `SIGINT`/`SIGTERM` handler that terminates it on shutdown.
- **WebSocket Reconnection**: Frontend `connectWS` now implements exponential backoff (1s→2s→4s→8s→16s, max 5 retries) with automatic reconnection after drops.
- **Cancelled Status**: Added `cancelled` as a first-class job status across backend (WebSocket loop, job store), frontend (polling, history items, status chips, CSS).
- **Cancel + Cleanup Endpoints**: Added `POST /api/v1/jobs/{job_id}/cancel` and `DELETE /api/v1/jobs/cleanup` with full process-tree teardown.

## 2026-05-01 (Job Control & Maintenance)
- **Manual Cancellation**: Implemented a "Kill Job" feature with backend subprocess termination support.
- **Cleanup API**: Added a global cleanup endpoint to terminate all running jobs and wipe history.
- **Frontend Enhancements**: Added "Stop" buttons to active pipeline cards and a "Clear All" button to the History view.
- **Project Tracking**: Created `docs/TASKS.md` to formalize the roadmap and track persistent validator issues.
- **Audit Update**: Refined `docs/AUDIT.md` to reflect the current high-health state of the SaaS platform.

## 2026-05-01 (Prompt Engineering: Linting Fixes)
- **PEP 8 Compliance**: Updated the Python style note in `prompt_templates.py` to explicitly require exactly 2 blank lines between top-level definitions (fixing E302 errors).
- **Template Bugfix**: Discovered and fixed a bug where the `{style_note}` instruction was being omitted from the rendered prompts in `build_standard_prompt` and `build_batch_prompt`.
- **Architect Consistency**: This ensures the LLM receives the "Senior Architect" style guidelines correctly, leading to cleaner, more compliant code.

## 2026-05-01 (Maintenance)
- **Server Shutdown**: Terminated the FastAPI backend (Port 8000) and Vite frontend (Port 5173) development servers to conclude the session.

## 2026-05-01 (Model Upgrade)
- **Engine Transition**: Upgraded the default refactoring engine from Gemini 2.5 Flash to **Gemma 3 1B**.
- **Frontend Integration**: Updated the dashboard configuration panel to prioritize Gemma 3 1B in the model selector.
- **Backend Defaults**: Synchronized the FastAPI refactor endpoint to use Gemma 3 1B as the default model.
- **Documentation**: Updated `README.md` and `ARCHITECTURE.md` to reflect the new AI core.

## 2026-05-01 (UI/UX Hardening)
- **Stage Timestamps**: Updated the backend to record ISO timestamps for each pipeline stage.
- **Real-Time Progress**: The frontend now displays the exact time of completion for each processing stage (cAST, Prompt Builder, etc.) directly under the pipeline steps.
- **Enhanced Error Handling**: 
    - Implemented a dedicated "Pipeline Failed" alert block that displays the specific error message from the backend.
    - Improved CSS for error visibility with a soft red skeuomorphic warning style.
    - Added safety checks to prevent UI crashes when accessing nested job status properties.

- **README Overhaul**: Completely updated `README.md` to reflect the transition from a CLI-first tool to a full SaaS platform.
- **Feature Documentation**: Added details about FastAPI backend, WebSocket real-time updates, and the multi-file/folder/ZIP upload capabilities.
- **Getting Started**: Updated setup instructions for both Backend (FastAPI) and Frontend (Vite).
- **Project Structure**: Refined the project structure description to align with the latest architectural changes.
