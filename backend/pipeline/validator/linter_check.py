# pipeline/validator/linter_check.py
import subprocess
import sys

def lint_with_pylint(file_path: str) -> tuple[bool, str]:
    """Run pylint and return score + output."""
    result = subprocess.run(
        [sys.executable, "-m", "pylint", file_path, "--disable=all", 
         "--enable=E,F"],  # Errors and Failures only
        capture_output=True,
        text=True,
    )
    return result.returncode == 0, result.stdout

def lint_with_flake8(file_path: str) -> tuple[bool, str]:
    """Run flake8 for simpler checks, invoked via sys.executable for venv compatibility."""
    result = subprocess.run(
        [sys.executable, "-m", "flake8", file_path, "--count", "--max-line-length=120"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0, result.stdout