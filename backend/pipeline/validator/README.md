# Stage 4 — Validator

Validates LLM-generated refactored Python code for correctness, structural
fidelity, and behavioral equivalence against the original source.

---

## Architecture

```
validator/
│
├── __init__.py               Public API surface
├── syntax_validator.py       ast.parse + py_compile dry-run
├── ast_comparator.py         Structural fingerprint diff
├── linter_check.py           flake8 (primary) + pylint (optional)
├── test_runner.py            pytest runner (when tests exist)
├── run_validation.py         Orchestration: run_validation() + validate_repo()
├── validation_report.py      .txt and .json report writers
│
└── functional/               Dynamic behavioral testing engine
    ├── __init__.py
    ├── behavior_capture.py   Safe module import + callable extraction
    ├── input_generator.py    Type-aware diverse input generation
    ├── test_executor.py      Timeout-protected function execution
    ├── replay_test_builder.py Capture→replay behavioral equivalence
    ├── property_test_builder.py Determinism, type-stability, exception contract
    └── result_analyzer.py    Deep equality + aggregation
```

---

## Validation Pipeline

Every file pair is processed through two sequential stages.

### Stage A — Static Checks

| Check | Tool | Failure severity |
|---|---|---|
| Syntax | `ast.parse` + `py_compile` | **Error** — stops pipeline immediately |
| AST structure | Custom fingerprinter | Warning |
| Lint | `flake8` (errors + warnings) | Warning |
| pytest | Existing test suite, if any | Warning |

### Stage B — Dynamic / Behavioral Checks

Runs only when static syntax passes.

| Check | What it verifies |
|---|---|
| **Replay testing** | Run both modules with the same generated inputs; compare outputs exactly |
| **Determinism** | Calling `f(x)` twice returns the same result |
| **Type stability** | Return type is the same between original and refactored |
| **Exception contract** | If original raises `ValueError`, refactored must too |
| **Idempotence** (opt-in) | If `f(f(x)) == f(x)` originally, it still holds |

---

## Usage

### Validate a single file pair

```python
from validator import run_validation, generate_report

result = run_validation(
    original_file   = Path("backend/input/order_service.py"),
    refactored_file = Path("backend/output/order_service.refactored.py"),
)

generate_report(result, Path("reports/order_service_report.txt"))
print(result.passed, result.pass_rate, result.severity)
```

### Validate an entire repository

```python
from validator import validate_repo

results = validate_repo(
    original_dir   = Path("backend/input/"),
    refactored_dir = Path("backend/output/"),
    report_dir     = Path("backend/output/reports/"),
)

# results is a list of dicts, one per original file:
# [
#   {"file": "foo.py", "status": "PASS", "pass_rate": 1.0,  "error": None,    ...},
#   {"file": "bar.py", "status": "FAIL", "pass_rate": 0.75, "error": "...",   ...},
#   {"file": "baz.py", "status": "SKIP", "pass_rate": None, "error": "...",   ...},
# ]
```

### CLI — single file

```bash
python -m validator.run_validation file \
  --original  backend/input/order_service.py \
  --refactored backend/output/order_service.refactored.py \
  --report     reports/order_service.txt \
  --json-report reports/order_service.json
```

### CLI — repository

```bash
python -m validator.run_validation repo \
  --original-dir  backend/input/ \
  --refactored-dir backend/output/ \
  --report-dir    backend/output/reports/
```

---

## ValidationResult fields

| Field | Type | Description |
|---|---|---|
| `passed` | `bool` | `True` only when all checks pass |
| `severity` | `str` | `"pass"` / `"warning"` / `"error"` |
| `pass_rate` | `float` | Functional test pass rate (0.0–1.0) |
| `checks` | `dict` | `{check_name: (bool, message)}` |
| `functional_detail` | `dict` | Per-function breakdown + property failures |
| `file` | `str` | Base filename of the validated pair |

---

## validate_repo result dict

```python
{
    "file":      "order_service.py",
    "status":    "PASS",          # PASS | FAIL | SKIP
    "pass_rate": 1.0,             # None for SKIP
    "severity":  "pass",          # pass | warning | error | skip
    "error":     None,            # first failed check message, or None
    "checks": {
        "syntax":        True,
        "ast_structure": True,
        "linting":       True,
        "functional":    True,
    }
}
```

---

## Severity levels

| Severity | Meaning | Recommended action |
|---|---|---|
| `pass` | All checks green | Accept refactored file |
| `warning` | Non-fatal issues (lint, minor AST drift, partial test pass) | Review + optionally re-send to LLM |
| `error` | Syntax broken | Automatically re-send to LLM |
| `skip` | No refactored counterpart found | Check LLM agent output |

---

## Input generation strategy

The input generator produces **N diverse samples per function**, always
including edge cases:

- **int / float**: `0, 1, -1, INT_MAX, INT_MIN` + random values
- **str**: `""`, `" "`, `"hello"`, `"123"`, long string + random
- **list**: `[]`, `[0]`, `[1,2,3]` + random length
- **bool**: `True` and `False`
- **Typed generics** (`List[X]`, `Dict[K,V]`, `Optional[T]`, `Tuple[…]`): fully resolved recursively
- **Default values**: reused 20 % of the time to exercise the happy path
- **Fallback** (no annotation): `0`, `1`, `"test"`, `True`, `3.14`

---

## Safety guarantees

- **Crash isolation**: a crash validating file A never aborts file B
- **Timeout**: every function call is limited to `func_timeout` seconds (default 5 s)
- **Import isolation**: modules are loaded into unique `sys.modules` slots; `sys.path` additions are cleaned up after each import
- **No forced kills**: thread-based timeout returns immediately (`shutdown(wait=False)`) — background threads may linger but do not block the pipeline
- **Graceful degradation**: missing flake8 / pylint → check skipped with `True`; missing test directory → pytest check skipped

---

## Running the test suite

```bash
# From the project root
python backend/run_tests.py

# Or directly
python -m pytest backend/tests/test_validator.py -v
```

95 tests across 12 test classes covering every module and edge case.

---

## Research extensions

To make this publishable as a research tool:

1. **Mutation testing** — automatically mutate the refactored code and verify the validator catches the mutations (tests the tests).
2. **LLM-guided input generation** — use a second LLM call to generate domain-aware inputs based on function docstrings (e.g. "this function expects a sorted list").
3. **Semantic diff report** — use AST diffing libraries (`gumtree`, `ast-diff`) to produce a human-readable explanation of *what changed* structurally.
4. **Re-refactoring loop** — wire `validate_repo` back to the LLM agent so files with `severity == "error"` are automatically re-queued with the failure report as additional context.
5. **Coverage measurement** — instrument the refactored module with `coverage.py` during replay testing to surface untested branches.
