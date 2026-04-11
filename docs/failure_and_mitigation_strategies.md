# Refactoring Pipeline: Failures and Mitigation Strategies

This document analyzes recent failures encountered during the end-to-end refactoring process and proposes technical strategies to mitigate these issues in future iterations.

---

## 🛑 1. Observed Failures

### 1.1. Top-Level Code Omission (e.g., `round_robin.py`)
*   **Symptom**: The pipeline executes successfully but produces a `.refactored.py` file identical to the original, with 0 prompts generated.
*   **Root Cause**: The current `cAST` (Stage 1) implementation specifically targets `ast.FunctionDef` and `ast.ClassDef` nodes. If a file contains only top-level script logic (loops, assignments, etc. outside of functions), it finds 0 "transformable chunks."
*   **Impact**: Critical production logic in scripts remains unrefactored, losing the opportunity for quality enhancement.

### 1.2. Nested Chunk Duplication
*   **Symptom**: Refactored files contained duplicated code blocks (e.g., `f()` function appearing both as part of `solve()` and as a standalone block).
*   **Root Cause**: If a function is defined inside another function, both were being treated as separate chunks. Replacing the inner one first, then the outer one (which *also* contains the refactored inner one), caused overlapping replacements and file corruption.
*   **Impact**: Syntax errors, redundant code, and broken logic in the final output.

### 1.3. Loss of Global Architectural Context
*   **Symptom**: In early versions, the LLM refactored items in isolation, occasionally breaking dependencies or violating system-wide design patterns (e.g., renaming a variable that is used elsewhere in the file).
*   **Root Cause**: Chunks were passed to the LLM with only their local source code, providing no visibility into the surrounding file structure.
*   **Impact**: Reduced adherence to SOLID/DRY principles and potential breaking changes.

---

## 🛡️ 2. Mitigation Strategies

### 2.1. Module-Level & "Main" Block Detection
*   **Status**: 🗓️ Planned / Investigation
*   **Strategy**: Update `cAST` to detect "Module-Level" code segments as a fallback chunk.

### 2.2. Robust Nested Filtering (Implemented)
*   **Status**: ✅ Implemented
*   **Strategy**: Implement a "Scope-Aware Filter" in the LLM Agent.

### 2.3. Global Architectural Context Injection (Implemented)
*   **Status**: ✅ Implemented
*   **Strategy**: Every individual prompt must be "Architecture-Aware."

### 2.4. Validation Gate (Implemented)
*   **Status**: ✅ Implemented (Stage 4)
*   **Strategy**: Automated multi-tier verification (Syntax, AST, Linter) following code reassembly.

---

## 📈 3. Continuous Improvement Loop

1.  **Stage 1 Update**: Enhance `cAST` to support "Loose Code" chunks.
2.  **Semantic Diffing**: In future versions, use AST-based diffing to verify that logic hasn't changed despite the refactoring.
3.  **Frontend Dashboard**: Visualize pipeline progress and validation reports.
