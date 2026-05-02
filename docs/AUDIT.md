# Refactoring Pipeline Audit - May 2026

## 1. Resolved Issues

### 1.1 Model Identity Mismatch
- **Problem**: The frontend was sending `gemma-3-1b` while the Google AI API expected `gemma-3-1b-it`. This resulted in `404 NOT_FOUND` errors.
- **Fix**: Updated both `main.py` (backend) and `App.jsx` (frontend) to use `gemma-3-1b-it` as the default identifier.

### 1.2 Pipeline Timeouts
- **Problem**: Large projects or files requiring multiple retries (due to 429/503 rate limits) were hitting a hard 10-minute timeout in `main.py`, causing the pipeline to be killed while still processing.
- **Fix**: Increased the global `communicate` timeout to **30 minutes** and improved the error messaging to reflect this.

### 1.3 Persistent Linting Errors (E302, etc.)
- **Problem**: Even successful refactorings were failing validation due to style issues like "expected 2 blank lines, found 1".
- **Fix**: Integrated a new **Stage 3.5: Lint Fix** into `orchestrate.py`. This stage runs `ruff format` and `ruff check --fix` on the refactored code before it reaches the final validator. This ensures the output is PEP 8 compliant by default.

### 1.5 Real-Time Stage Updates
- **Problem**: UI was using estimated timers, leading to a "stuck" Validator stage even after the backend finished.
- **Fix**: Replaced timers with a real-time event-driven system. The orchestrator now emits `::STAGE::n` markers which the backend reads and broadcasts via WebSockets immediately.
- **Outcome**: The UI is now perfectly synchronized with actual backend progress.

### 1.6 LLM Quality & Documentation Enforcement
- **Problem**: Simple files showed "0 lines changed" because the LLM was too conservative.
- **Fix**: Updated `prompt_templates.py` to require mandatory PEP 484 type hints and PEP 257 docstrings for all functions.
- **Outcome**: Refactorings now consistently add value even to well-structured code.

### 1.7 Job-Specific Output Isolation
- **Problem**: Concurrent jobs were overwriting each other in a shared `output/` directory.
- **Fix**: Implemented unique output folders for every job (`backend/output/<job_id>`).
- **Outcome**: Complete data isolation and reliable result retrieval.

## 2. Infrastructure Status
- **Backend**: Running on port 8000.
- **Frontend**: Running on port 5173.
- **Model**: Defaulting to `gemma-3-1b-it` (Gemma 3 1B Instruction Tuned).
- **Linter**: `flake8` for validation, `ruff` for auto-fixing.

## 3. Next Steps
- Implement batch processing for multiple uploaded files to optimize LLM usage.
- Add real-time log streaming via WebSocket instead of timed stage advancement.
