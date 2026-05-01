# 📋 Project Task Board

This document tracks identified issues, planned features, and technical debt for the AI Refactoring Pipeline.

## 🔴 High Priority (Bugs & Stability)

- [x] **Functional Validator Dependency Resolution**: Stage 4 often fails because it cannot resolve local/project-level imports in the `backend/input/uploads` directory.
    - *Fix*: `_save_uploads` now preserves full directory trees for both `.py` and `.zip` uploads.
- [x] **Object Identity in Validator**: The functional validator can be non-deterministic when comparing coroutines or generators.
    - *Fix*: Normalized `repr` comparison logic in `outputs_match` to strip memory addresses.
- [x] **Process Leakage**: Ensure that every subprocess started by `orchestrate.py` is correctly reaped, especially after a "Kill" signal.
    - *Fix*: Added `_kill_process_tree()` using `taskkill /T` on Windows, and SIGTERM signal handlers in `orchestrate.py`.
- [x] **WebSocket Reconnection**: Implement exponential backoff for the frontend WebSocket client to handle server restarts gracefully.
    - *Fix*: `connectWS` now retries up to 5 times with 1s → 2s → 4s → 8s → 16s backoff.

## 🟡 Medium Priority (Features & UX)

- [x] **Recursive Upload Support**: Allow users to upload nested folders and maintain their structure throughout the pipeline.
    - *Fix*: `_save_uploads` preserves `webkitdirectory` paths and ZIP internal trees.
- [ ] **Custom Model Input**: Add an "Other/Custom" option in the configuration to allow users to input arbitrary model names.
- [ ] **Validation Report Enhancements**: Add visualization for AST diffs and functional test coverage in the UI.
- [ ] **Download All**: Add a button to download the entire refactored codebase as a ZIP file.

## 🟢 Low Priority (Maintenance)

- [ ] **Linting Automation**: Run `black` or `ruff` automatically on the refactored output before validation.
- [ ] **Unit Tests for Pipeline**: Implement comprehensive tests for `cAST` and `PromptBuilder` logic.
- [ ] **Dark Mode**: Add a toggle for a dark-themed Neumorphic UI.
