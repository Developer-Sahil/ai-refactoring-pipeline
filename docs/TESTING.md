# Testing Strategy - AI Refactoring Pipeline

## Overview
The AI Refactoring Pipeline uses a multi-stage validation process to ensure the integrity of refactored code.

## 1. Unit Testing
- Located in `backend/tests/`.
- Validates individual pipeline components.

## 2. Stage 4 Validator (Automated)
- **Syntax Check**: Ensures refactored code is valid Python.
- **AST Comparison**: Verifies structural integrity.
- **Functional Validation**:
    - **Behavior Capture**: Records state transitions.
    - **Property Testing**: Generates random inputs for edge-case coverage.
    - **Replay**: Compares outputs between original and refactored code.

## 3. Manual UI Audit
- Validates the Neumorphic design system and pipeline progress indicators on the dashboard.

## Commands
- Run all tests: `pytest backend/tests/`
- Run validation on a file: `python backend/pipeline/validator/run_validation.py --path <path>`
