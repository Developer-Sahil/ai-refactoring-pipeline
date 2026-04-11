# Stage 4: Validator

The Validator ensures that the refactored code produced by the LLM is safe, syntactically correct, and preserves the original logical structure.

## 🛠️ Key Components

-   **Syntax Validator**: Uses `ast.parse` and `py_compile` (dry-run) to ensure the code is valid Python.
-   **AST Comparator**: Compares the abstract syntax tree of the original and refactored code to ensure that core function signatures and class structures remain intact.
-   **Linter Check**: Runs `flake8` to enforce PEP8 standards and catch potential runtime issues early.
-   **Validation Report**: Generates a comprehensive summary of the check results in both text and JSON formats.

## 🚀 Usage

```bash
python -m validator.run_validation --original path/to/source.py --refactored path/to/refactored.py --report path/to/report.txt
```

## 📋 Severity Levels

1.  **PASS**: All checks passed.
2.  **WARNING**: Minor linting or style issues found, but code is functional.
3.  **FAIL**: Syntax errors or significant structural deviations detected.
