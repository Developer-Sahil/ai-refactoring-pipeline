# pipeline/validator/test_runner.py
"""
pytest runner: execute an existing test suite against the refactored module.

If no test directory exists the check is silently skipped (returns True).
This is intentional — most repositories refactored by the pipeline will
*not* have pre-existing tests.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run_pytest(
    source_file: Path,
    test_dir:    Path | None = None,
    timeout:     int  = 60,
) -> tuple[bool, str]:
    """
    Run pytest in *test_dir* (defaults to ``source_file.parent``).

    Returns ``(True, output)`` when all tests pass.
    Returns ``(False, output)`` on failures.
    Returns ``(True, "No test directory found — skipped")`` when absent.
    """
    if test_dir is None:
        test_dir = source_file.parent

    if not Path(test_dir).exists():
        return True, "No test directory found — skipped"

    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "pytest",
                str(test_dir),
                "-v",
                "--tb=short",
                "--no-header",
                "-q",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, f"pytest timed out after {timeout}s"
    except FileNotFoundError:
        return True, "pytest not installed — skipped"

    output = result.stdout + result.stderr
    return result.returncode == 0, output
