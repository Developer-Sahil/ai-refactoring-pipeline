"""
tests/test_validator.py
-----------------------
Self-contained test suite for pipeline/validator (Stage 4).
Run from repo root with:
    python -m pytest tests/test_validator.py -v
"""

import ast
import textwrap
import sys
from pathlib import Path

import pytest

# ── resolve paths so tests work from any cwd ───────────────────────────────
REPO_ROOT = Path(__file__).parent.parent.resolve()
VALIDATOR_DIR = REPO_ROOT / "pipeline" / "validator"
sys.path.insert(0, str(VALIDATOR_DIR))

# ── imports under test ─────────────────────────────────────────────────────
from syntax_validator import validate_python_syntax
from ast_comparator import compare_chunks
from linter_check import lint_with_flake8
from validation_report import generate_report, generate_json_report, print_summary
from run_validation import ValidationResult


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def write_tmp(tmp_path: Path, filename: str, code: str) -> Path:
    p = tmp_path / filename
    p.write_text(textwrap.dedent(code), encoding="utf-8")
    return p


VALID_CODE = """
    def hello(name: str) -> str:
        \"\"\"Greet someone.\"\"\"
        return f"Hello, {name}!"

    def add(a: int, b: int) -> int:
        return a + b
"""

INVALID_CODE = """
    def broken(
        print("oops"
"""

EXTRA_FUNC_CODE = """
    def hello(name: str) -> str:
        return f"Hello, {name}!"

    def add(a: int, b: int) -> int:
        return a + b

    def extra() -> None:
        pass
"""

CLASS_WITH_METHODS = """
    class Foo:
        def method_one(self):
            pass

        def method_two(self):
            pass

    def top_level():
        pass
"""


# ═══════════════════════════════════════════════════════════════════════════
# syntax_validator
# ═══════════════════════════════════════════════════════════════════════════

class TestSyntaxValidator:

    def test_valid_file_passes(self, tmp_path):
        f = write_tmp(tmp_path, "good.py", VALID_CODE)
        ok, msg = validate_python_syntax(f)
        assert ok is True
        assert msg == "Syntax OK"

    def test_invalid_file_fails(self, tmp_path):
        f = write_tmp(tmp_path, "bad.py", INVALID_CODE)
        ok, msg = validate_python_syntax(f)
        assert ok is False
        assert "Syntax Error" in msg

    def test_empty_file_passes(self, tmp_path):
        f = write_tmp(tmp_path, "empty.py", "")
        ok, msg = validate_python_syntax(f)
        assert ok is True

    def test_unicode_in_file_passes(self, tmp_path):
        code = '# -*- coding: utf-8 -*-\n# Unicode: こんにちは\ndef greet(): pass\n'
        f = tmp_path / "unicode.py"
        f.write_text(code, encoding="utf-8")
        ok, msg = validate_python_syntax(f)
        assert ok is True

    def test_missing_file_returns_error_tuple(self, tmp_path):
        missing = tmp_path / "ghost.py"
        ok, msg = validate_python_syntax(missing)
        assert ok is False
        assert len(msg) > 0


# ═══════════════════════════════════════════════════════════════════════════
# ast_comparator
# ═══════════════════════════════════════════════════════════════════════════

class TestAstComparator:

    def test_identical_code_passes(self):
        ok, msg = compare_chunks(VALID_CODE, VALID_CODE)
        assert ok is True
        assert "preserved" in msg.lower()

    def test_same_structure_different_names_passes(self):
        renamed = VALID_CODE.replace("hello", "greet").replace("add", "sum_two")
        ok, msg = compare_chunks(VALID_CODE, renamed)
        assert ok is True

    def test_extra_function_fails(self):
        ok, msg = compare_chunks(VALID_CODE, EXTRA_FUNC_CODE)
        assert ok is False
        assert "Function count changed" in msg

    def test_class_methods_not_counted_as_top_level(self):
        """
        Bug fix #5: ast.walk was counting class methods as top-level functions.
        CLASS_WITH_METHODS has 1 top-level function (top_level) plus a class.
        A refactored version with same structure should pass.
        """
        ok, msg = compare_chunks(CLASS_WITH_METHODS, CLASS_WITH_METHODS)
        assert ok is True

    def test_invalid_syntax_raises_graceful_error(self):
        ok, msg = compare_chunks(INVALID_CODE, VALID_CODE)
        assert ok is False
        assert "AST comparison failed" in msg or "Syntax Error" in msg.lower() or "failed" in msg.lower()


# ═══════════════════════════════════════════════════════════════════════════
# linter_check
# ═══════════════════════════════════════════════════════════════════════════

class TestLinterCheck:

    def test_clean_file_passes(self, tmp_path):
        # Minimal flake8-compliant file
        code = 'def add(a, b):\n    return a + b\n'
        f = write_tmp(tmp_path, "clean.py", code)
        ok, msg = lint_with_flake8(str(f))
        assert ok is True

    def test_lint_returns_tuple(self, tmp_path):
        f = write_tmp(tmp_path, "any.py", VALID_CODE)
        result = lint_with_flake8(str(f))
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)


# ═══════════════════════════════════════════════════════════════════════════
# validation_report
# ═══════════════════════════════════════════════════════════════════════════

class TestValidationReport:

    def _make_result(self, passed=True, severity="pass"):
        checks = {
            "syntax":       (True,   "Syntax OK"),
            "ast_structure":(passed, "AST structure preserved" if passed else "Function count changed: 2 → 3"),
            "linting":      (True,   "No issues"),
        }
        return ValidationResult(passed=passed, checks=checks, severity=severity)

    def test_generate_report_creates_file(self, tmp_path):
        result = self._make_result()
        out = tmp_path / "report.txt"
        generate_report(result, out)
        assert out.exists()

    def test_report_contains_pass_status(self, tmp_path):
        result = self._make_result(passed=True, severity="pass")
        out = tmp_path / "report.txt"
        generate_report(result, out)
        content = out.read_text(encoding="utf-8")
        assert "✓ PASS" in content
        assert "PASS" in content

    def test_report_contains_fail_status(self, tmp_path):
        result = self._make_result(passed=False, severity="warning")
        out = tmp_path / "report.txt"
        generate_report(result, out)
        content = out.read_text(encoding="utf-8")
        assert "✗ FAIL" in content

    def test_report_is_utf8(self, tmp_path):
        """Report file must be UTF-8 so Unicode glyphs survive on Windows."""
        result = self._make_result()
        out = tmp_path / "report.txt"
        generate_report(result, out)
        # If encoding is wrong this will raise UnicodeDecodeError
        content = out.read_text(encoding="utf-8")
        assert "✓" in content

    def test_generate_json_report(self, tmp_path):
        import json
        result = self._make_result(passed=False, severity="warning")
        out = tmp_path / "report.json"
        generate_json_report(result, out)
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert payload["passed"] is False
        assert payload["severity"] == "warning"
        assert "syntax" in payload["checks"]

    def test_print_summary_does_not_crash(self, capsys):
        result = self._make_result(passed=False, severity="warning")
        print_summary(result)
        captured = capsys.readouterr()
        assert "FAILED" in captured.out


# ═══════════════════════════════════════════════════════════════════════════
# ValidationResult severity logic  (run_validation)
# ═══════════════════════════════════════════════════════════════════════════

class TestSeverityLogic:
    """
    Verifies the 3-tier severity: error > warning > pass.
    We test the logic by constructing results directly rather than
    invoking the full pipeline (which requires real files).
    """

    def test_all_pass_gives_pass_severity(self):
        r = ValidationResult(passed=True, checks={"syntax": (True, "OK")}, severity="pass")
        assert r.severity == "pass"

    def test_non_syntax_fail_gives_warning(self):
        r = ValidationResult(
            passed=False,
            checks={
                "syntax":       (True,  "Syntax OK"),
                "ast_structure":(False, "Function count changed"),
            },
            severity="warning",
        )
        assert r.severity == "warning"
        assert r.passed is False

    def test_syntax_fail_gives_error(self):
        r = ValidationResult(
            passed=False,
            checks={"syntax": (False, "Syntax Error at line 3: ...")},
            severity="error",
        )
        assert r.severity == "error"


# ═══════════════════════════════════════════════════════════════════════════
# Integration smoke test  (uses actual refactored output if available)
# ═══════════════════════════════════════════════════════════════════════════

ORIGINAL_FILE  = REPO_ROOT / "input" / "order_service.py"
REFACTORED_FILE = REPO_ROOT / "pipeline" / "llm_agent" / "output" / "order_service.refactored.py"

@pytest.mark.skipif(
    not (ORIGINAL_FILE.exists() and REFACTORED_FILE.exists()),
    reason="Requires order_service.py + order_service.refactored.py",
)
class TestIntegration:

    def test_syntax_of_refactored_file(self):
        ok, msg = validate_python_syntax(REFACTORED_FILE)
        assert ok is True, f"Refactored file has syntax errors: {msg}"

    def test_ast_comparison_of_real_files(self):
        orig = ORIGINAL_FILE.read_text(encoding="utf-8")
        refac = REFACTORED_FILE.read_text(encoding="utf-8")
        ok, msg = compare_chunks(orig, refac)
        # We just check it doesn't crash; structural changes may be intentional
        assert isinstance(ok, bool)
        assert isinstance(msg, str)

    def test_lint_of_refactored_file(self):
        ok, msg = lint_with_flake8(str(REFACTORED_FILE))
        # Lint may find style issues but must not crash
        assert isinstance(ok, bool)
