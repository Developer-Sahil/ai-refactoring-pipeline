# pipeline/validator/__init__.py
"""
Stage 4: Validator

Public API
----------
run_validation(original_file, refactored_file, ...)
    Validate a single (original, refactored) file pair.
    Returns a ValidationResult with .passed, .severity, .pass_rate, .checks.

validate_repo(original_dir, refactored_dir, ...)
    Match and validate every file in a directory.
    Returns a list of structured result dicts (PASS / FAIL / SKIP per file).

ValidationResult
    Dataclass holding the full outcome of one file's validation.

generate_report(result, path)
    Write a human-readable .txt report.

generate_json_report(result, path)
    Write a machine-readable .json report.
"""

from .run_validation   import run_validation, validate_repo, ValidationResult
from .validation_report import generate_report, generate_json_report, print_summary

__all__ = [
    "run_validation",
    "validate_repo",
    "ValidationResult",
    "generate_report",
    "generate_json_report",
    "print_summary",
]
