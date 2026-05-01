# 📋 Project Task Board

This document tracks identified issues, planned features, and technical debt for the AI Refactoring Pipeline.

## 🔴 High Priority (Bugs & Stability)

- [ ] **Functional Validator Dependency Resolution**: Stage 4 often fails because it cannot resolve local/project-level imports in the `backend/input/uploads` directory.
    - *Proposed Fix*: Implement recursive file preservation for uploads to maintain the full project tree structure.
- [ ] **Object Identity in Validator**: The functional validator can be non-deterministic when comparing coroutines or generators.
    - *Proposed Fix*: Normalize `repr` comparison logic or use state-snapshotting.
- [ ] **Process Leakage**: Ensure that every subprocess started by `orchestrate.py` is correctly reaped, especially after a "Kill" signal.
- [ ] **WebSocket Reconnection**: Implement exponential backoff for the frontend WebSocket client to handle server restarts gracefully.

## 🟡 Medium Priority (Features & UX)

- [ ] **Recursive Upload Support**: Allow users to upload nested folders and maintain their structure throughout the pipeline.
- [ ] **Custom Model Input**: Add an "Other/Custom" option in the configuration to allow users to input arbitrary model names.
- [ ] **Validation Report Enhancements**: Add visualization for AST diffs and functional test coverage in the UI.
- [ ] **Download All**: Add a button to download the entire refactored codebase as a ZIP file.

## 🟢 Low Priority (Maintenance)

- [ ] **Linting Automation**: Run `black` or `ruff` automatically on the refactored output before validation.
- [ ] **Unit Tests for Pipeline**: Implement comprehensive tests for `cAST` and `PromptBuilder` logic.
- [ ] **Dark Mode**: Add a toggle for a dark-themed Neumorphic UI.
