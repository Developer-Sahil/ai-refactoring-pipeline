# pipeline/validator/syntax_validator.py
"""
Syntax validation: verify a .py file can be parsed and compiled cleanly.

Two complementary checks are run:
1. ``ast.parse``    — catches parse-time syntax errors with line info.
2. ``py_compile``   — runs a dry-run compilation to also surface
                      encoding declarations and certain edge-case errors
                      that ast.parse misses.
"""
from __future__ import annotations

import ast
import py_compile
import tempfile
from pathlib import Path


def validate_python_syntax(file_path: Path) -> tuple[bool, str]:
    """
    Return ``(True, "Syntax OK")`` or ``(False, "<error detail>")``.

    Both checks must pass.  The AST parse is tried first because it
    provides the most informative error message (line number + column).
    """
    file_path = Path(file_path)

    # --- 1. AST parse ---------------------------------------------------
    try:
        source = file_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return False, f"File not found: {file_path}"
    except UnicodeDecodeError as exc:
        return False, f"Encoding error reading file: {exc}"

    try:
        ast.parse(source, filename=str(file_path))
    except SyntaxError as exc:
        return False, (
            f"SyntaxError at line {exc.lineno}, col {exc.offset}: {exc.msg}"
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"AST parse failed: {type(exc).__name__}: {exc}"

    # --- 2. py_compile dry run ------------------------------------------
    try:
        with tempfile.NamedTemporaryFile(suffix=".pyc", delete=True) as tmp:
            py_compile.compile(str(file_path), cfile=tmp.name, doraise=True)
    except py_compile.PyCompileError as exc:
        return False, f"Compile error: {exc}"
    except Exception:
        # py_compile can raise OSError on path edge cases; not critical
        pass

    return True, "Syntax OK"
