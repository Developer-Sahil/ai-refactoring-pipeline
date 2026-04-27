# pipeline/validator/linter_check.py
"""
Linting checks: flake8 (primary) with pylint as an optional secondary pass.

Both linters are invoked via ``sys.executable -m <tool>`` so the correct
virtual-environment binary is always used — no PATH assumptions needed.

Graceful degradation
--------------------
If a linter is not installed it is simply skipped (the check is marked as
passing with an informational message) so the pipeline keeps running even
in minimal environments.
"""
from __future__ import annotations

import subprocess
import sys


# ---------------------------------------------------------------------------
# flake8 (primary)
# ---------------------------------------------------------------------------

def lint_with_flake8(file_path: str) -> tuple[bool, str]:
    """
    Run flake8 on *file_path*.

    Checks for:
    - Syntax / undefined-name errors  (E9xx, F821, F823)
    - All other errors + warnings     (E, W, F)
    - Line length up to 120 chars     (--max-line-length=120)

    Returns ``(True, output)`` when flake8 exits with code 0 (no issues).
    Returns ``(False, output)`` when issues were found.
    Returns ``(True, "flake8 not installed — skipped")`` when unavailable.
    """
    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "flake8",
                file_path,
                "--count",
                "--max-line-length=120",
                "--statistics",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        return True, "flake8 not installed — skipped"
    except subprocess.TimeoutExpired:
        return False, "flake8 timed out"

    output = (result.stdout + result.stderr).strip()

    if result.returncode == 0:
        return True, "No flake8 issues"

    # `sys.executable -m flake8` won't raise FileNotFoundError when flake8 is
    # absent; instead Python prints "No module named flake8" to stderr and
    # exits with code 1.  Treat this the same as FileNotFoundError.
    if "no module named" in output.lower():
        return True, "flake8 not installed — skipped"

    # Return code 1 = style issues found; anything else = internal error
    return False, output or "flake8 reported issues (no output captured)"


# ---------------------------------------------------------------------------
# pylint (optional, errors + fatals only)
# ---------------------------------------------------------------------------

def lint_with_pylint(file_path: str) -> tuple[bool, str]:
    """
    Run pylint on *file_path* with only error (E) and fatal (F) messages
    enabled.  Warnings and conventions are deliberately suppressed so this
    check matches the *correctness* bar, not the style bar.

    Returns ``(True, "pylint not installed — skipped")`` when unavailable.
    """
    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "pylint",
                file_path,
                "--disable=all",
                "--enable=E,F",
                "--output-format=text",
                "--score=no",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError:
        return True, "pylint not installed — skipped"
    except subprocess.TimeoutExpired:
        return False, "pylint timed out"

    output = (result.stdout + result.stderr).strip()

    if "no module named" in output.lower():
        return True, "pylint not installed — skipped"

    # pylint exit codes: 0=ok, 1=fatal, 2=error, 4=warning, 8=refactor, 16=convention
    # Bit mask: any of 1 or 2 means errors/fatals were found
    if result.returncode & 0b00000011:
        return False, output or "pylint found errors"
    return True, "No pylint errors"
