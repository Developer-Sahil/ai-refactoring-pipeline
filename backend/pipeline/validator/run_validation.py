# pipeline/validator/run_validation.py
import json
from pathlib import Path
from typing import NamedTuple

try:
    # Package mode: imported as pipeline.validator.run_validation
    from .syntax_validator import validate_python_syntax
    from .ast_comparator import compare_chunks
    from .test_runner import run_pytest
    from .linter_check import lint_with_flake8
    from .validation_report import generate_report, print_summary
except ImportError:
    # Standalone / sys.path mode (tests, direct execution)
    from syntax_validator import validate_python_syntax
    from ast_comparator import compare_chunks
    from test_runner import run_pytest
    from linter_check import lint_with_flake8
    from validation_report import generate_report, print_summary

class ValidationResult(NamedTuple):
    passed: bool
    checks: dict[str, tuple[bool, str]]  # check_name -> (passed, message)
    severity: str  # "error", "warning", "pass"

def run_validation(
    original_file: Path,
    refactored_file: Path,
    test_dir: Path = None,
) -> ValidationResult:
    """Execute all validation checks."""
    
    checks = {}
    
    # 1. Syntax validation (hard requirement)
    print("→ Checking syntax...")
    passed, msg = validate_python_syntax(refactored_file)
    checks["syntax"] = (passed, msg)
    if not passed:
        return ValidationResult(False, checks, "error")
    
    # 2. AST structure comparison
    print("→ Comparing AST structure...")
    orig_code = original_file.read_text(encoding="utf-8")
    refac_code = refactored_file.read_text(encoding="utf-8")
    passed, msg = compare_chunks(orig_code, refac_code)
    checks["ast_structure"] = (passed, msg)
    
    # 3. Lint check
    print("→ Running linter...")
    passed, msg = lint_with_flake8(str(refactored_file))
    checks["linting"] = (passed, msg)
    
    # 4. Test execution (if tests exist)
    if test_dir and test_dir.exists():
        print("→ Running pytest...")
        passed, msg = run_pytest(refactored_file, test_dir)
        checks["tests"] = (passed, msg)
    
    # Summary — three severity tiers:
    #   "error"   : syntax broken (already caught above, but guard here too)
    #   "warning" : non-fatal checks failed (lint, AST drift, test failures)
    #   "pass"    : everything green
    all_passed = all(v[0] for v in checks.values())
    syntax_ok = checks.get("syntax", (True,))[0]

    if not syntax_ok:
        severity = "error"
    elif not all_passed:
        severity = "warning"
    else:
        severity = "pass"

    return ValidationResult(all_passed, checks, severity)

# generate_report is now implemented in validation_report.py and imported above.

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Stage 4: Validate a refactored Python file.")
    parser.add_argument("--original",  required=True, help="Original source file")
    parser.add_argument("--refactored", required=True, help="Refactored source file")
    parser.add_argument("--tests", help="Test directory (optional)")
    parser.add_argument("--report", default="validation_report.txt", help="Output report path")
    parser.add_argument("--json-report", default=None, help="Optional JSON report path")

    args = parser.parse_args()
    result = run_validation(
        Path(args.original),
        Path(args.refactored),
        Path(args.tests) if args.tests else None,
    )

    generate_report(result, Path(args.report))

    if args.json_report:
        from .validation_report import generate_json_report
        generate_json_report(result, Path(args.json_report))

    print_summary(result)
    raise SystemExit(0 if result.passed else 1)