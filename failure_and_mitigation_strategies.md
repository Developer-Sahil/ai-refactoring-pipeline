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
*   **Strategy**: Update `cAST` to detect "Module-Level" code segments as a fallback chunk.
*   **Implementation**:
    1.  Identify all code residing in the global scope (outside classes/functions).
    2.  Explicitly detect `if __name__ == "__main__":` blocks.
    3.  Generate a "script" or "main" chunk type to ensure these areas are also refactored.

### 2.2. Robust Nested Filtering (Implemented)
*   **Strategy**: Implement a "Scope-Aware Filter" in the LLM Agent.
*   **Implementation**:
    1.  Sort all prompts by line range.
    2.  Before processing, check for inclusivity: If `Chunk A` is entirely contained within `Chunk B`, skip `Chunk A`'s dedicated prompt.
    3.  The LLM refactors `Chunk B` (the parent), which inherently includes the refactoring of `Chunk A`.

### 2.3. Global Architectural Context Injection (Implemented)
*   **Strategy**: Every individual prompt must be "Architecture-Aware."
*   **Implementation**:
    1.  Stage 2 (Prompt Builder) now reads the **full source file**.
    2.  The full file is injected as a "Global Context" block in the prompt instructions.
    3.  The LLM is instructed to "use the global context to ensure your changes are consistent with the rest of the file."

### 2.4. Senior Architect "Safe" Prompting
*   **Strategy**: Use high-confidence system prompts to prevent "hallucinations" or unnecessary changes.
*   **Implementation**:
    1.  Explicit "Constraints" block (e.g., "Do NOT change observable behavior," "Do NOT rename public APIs").
    2.  "Senior Software Architect" persona to enforce strict documentation and type-hinting standards.

---

## 📈 3. Continuous Improvement Loop

1.  **Stage 1 Update**: Enhance `cAST` to support "Loose Code" chunks.
2.  **Stage 4 Verification**: Implement an automated **Syntax Check** (e.g., `python -m compileall`) on the `.refactored.py` file before declaring success.
3.  **Semantic Diffing**: In future versions, use AST-based diffing to verify that logic hasn't changed despite the refactoring.
