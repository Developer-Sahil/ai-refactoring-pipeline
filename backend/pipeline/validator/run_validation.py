# pipeline/validator/run_validation.py
"""
Stage 4 — Validation engine.

Entry points
------------
run_validation(original_file, refactored_file, ...)
    Validate one (original, refactored) pair.  Runs static checks first;
    if syntax is broken the functional stage is skipped entirely.

validate_repo(original_dir, refactored_dir, ...)
    Match every ``file.py`` in *original_dir* to ``file.refactored.py``
    in *refactored_dir*, call ``run_validation`` for each pair, and return
    a structured report list suitable for dashboard display or CI gating.

Both functions are deliberately exception-safe: a crash inside one file's
validation never propagates to the rest of the batch.
"""
from __future__ import annotations

import json
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Relative imports (package mode) with sys.path fallback (standalone / tests)
# ---------------------------------------------------------------------------
try:
    from .syntax_validator  import validate_python_syntax
    from .ast_comparator    import compare_chunks
    from .linter_check      import lint_with_flake8
    from .test_runner       import run_pytest
    from .validation_report import generate_report, generate_json_report, print_summary
    from .functional        import (
        safe_import_module,
        capture_behavior,
        replay_against_refactored,
        run_all_property_checks,
        compute_aggregate,
    )
except ImportError:
    from syntax_validator  import validate_python_syntax   # type: ignore[no-redef]
    from ast_comparator    import compare_chunks            # type: ignore[no-redef]
    from linter_check      import lint_with_flake8          # type: ignore[no-redef]
    from test_runner       import run_pytest                # type: ignore[no-redef]
    from validation_report import generate_report, generate_json_report, print_summary  # type: ignore[no-redef]
    from functional        import (                          # type: ignore[no-redef]
        safe_import_module,
        capture_behavior,
        replay_against_refactored,
        run_all_property_checks,
        compute_aggregate,
    )


# ---------------------------------------------------------------------------
# Result data class
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    """
    Full outcome of validating one (original, refactored) file pair.

    Attributes
    ----------
    passed          True only when *all* checks pass.
    checks          Ordered dict of check_name → (passed, message).
    severity        "pass" | "warning" | "error"
    pass_rate       Functional test pass rate (0.0–1.0).
    functional_detail  Raw aggregate dict from result_analyzer.
    file            Basename of the validated file (for reporting).
    """
    passed:            bool
    checks:            dict[str, tuple[bool, str]]
    severity:          str
    pass_rate:         float = 1.0
    functional_detail: dict  = field(default_factory=dict)
    file:              str   = ""


# ---------------------------------------------------------------------------
# Single-file validator
# ---------------------------------------------------------------------------

def run_validation(
    original_file:    Path,
    refactored_file:  Path,
    test_dir:         Optional[Path] = None,
    run_functional:   bool = True,
    inputs_per_func:  int  = 6,
    func_timeout:     float = 5.0,
    run_properties:   bool = True,
) -> ValidationResult:
    """
    Run the full validation suite for one (original, refactored) pair.

    Static checks (always run)
    --------------------------
    1. Syntax validation
    2. AST structural comparison
    3. flake8 lint

    Dynamic checks (skipped when syntax is broken)
    -----------------------------------------------
    4. Replay-based behavioral equivalence testing
    5. Property checks (determinism, type-stability, exception contract)
    6. pytest (when *test_dir* is supplied and non-empty)
    """
    checks: dict[str, tuple[bool, str]] = {}
    functional_detail: dict = {}

    original_file   = Path(original_file)
    refactored_file = Path(refactored_file)

    # ------------------------------------------------------------------
    # 1. Syntax — hard gate; everything else depends on this
    # ------------------------------------------------------------------
    print(f"  [syntax]   {refactored_file.name}")
    ok, msg = validate_python_syntax(refactored_file)
    checks["syntax"] = (ok, msg)

    if not ok:
        return ValidationResult(
            passed=False, checks=checks,
            severity="error", pass_rate=0.0,
            file=original_file.name,
        )

    # ------------------------------------------------------------------
    # 2. AST structural comparison
    # ------------------------------------------------------------------
    print(f"  [ast]      comparing structure …")
    try:
        orig_code  = original_file.read_text(encoding="utf-8")
        refac_code = refactored_file.read_text(encoding="utf-8")
        ok, msg    = compare_chunks(orig_code, refac_code)
    except Exception as exc:  # noqa: BLE001
        ok, msg = False, f"AST comparison crashed: {exc}"
    checks["ast_structure"] = (ok, msg)

    # ------------------------------------------------------------------
    # 3. Lint
    # ------------------------------------------------------------------
    print(f"  [lint]     flake8 …")
    try:
        ok, msg = lint_with_flake8(str(refactored_file))
    except Exception as exc:  # noqa: BLE001
        ok, msg = False, f"Linter crashed: {exc}"
    checks["linting"] = (ok, msg)

    # ------------------------------------------------------------------
    # 4 & 5. Functional / behavioral testing
    # ------------------------------------------------------------------
    functional_pass_rate = 1.0

    if run_functional:
        print(f"  [behavior] importing modules …")
        orig_module,  orig_err  = safe_import_module(original_file)
        refac_module, refac_err = safe_import_module(refactored_file)

        if orig_module is None:
            checks["functional"] = (
                False,
                f"Could not import original: {orig_err}",
            )
        elif refac_module is None:
            checks["functional"] = (
                False,
                f"Could not import refactored: {refac_err}",
            )
        else:
            print(f"  [behavior] capturing original behavior …")
            try:
                test_bank = capture_behavior(
                    orig_module,
                    inputs_per_func=inputs_per_func,
                    timeout=func_timeout,
                )
                print(f"  [behavior] replaying on refactored …")
                replay_results = replay_against_refactored(
                    refac_module, test_bank, timeout=func_timeout,
                )

                prop_results: dict = {}
                if run_properties:
                    print(f"  [property] checking invariants …")
                    prop_results = run_all_property_checks(
                        orig_module, refac_module,
                        n=4, timeout=func_timeout,
                    )

                functional_detail = compute_aggregate(replay_results, prop_results)
                functional_pass_rate = functional_detail.get("pass_rate", 1.0)

                # Summarise into a single check entry
                total  = functional_detail["total_tests"]
                passed = functional_detail["passed_tests"]

                if total == 0:
                    # No testable functions found (e.g. module has no public funcs)
                    checks["functional"] = (True, "No testable functions found")
                else:
                    func_ok = (passed == total)
                    prop_fails = len(functional_detail.get("property_failures", []))
                    msg = (
                        f"{passed}/{total} tests passed "
                        f"({functional_pass_rate:.0%})"
                        + (f"; {prop_fails} property violation(s)" if prop_fails else "")
                    )
                    checks["functional"] = (func_ok and prop_fails == 0, msg)

            except Exception as exc:  # noqa: BLE001
                tb = traceback.format_exc(limit=6)
                checks["functional"] = (False, f"Functional testing crashed: {exc}\n{tb}")

    # ------------------------------------------------------------------
    # 6. pytest (optional)
    # ------------------------------------------------------------------
    if test_dir is not None:
        print(f"  [pytest]   running suite …")
        try:
            ok, msg = run_pytest(refactored_file, test_dir)
        except Exception as exc:  # noqa: BLE001
            ok, msg = False, f"pytest runner crashed: {exc}"
        checks["pytest"] = (ok, msg)

    # ------------------------------------------------------------------
    # Aggregate severity
    # ------------------------------------------------------------------
    syntax_ok  = checks.get("syntax",  (True,))[0]
    all_passed = all(v[0] for v in checks.values())

    if not syntax_ok:
        severity = "error"
    elif not all_passed:
        severity = "warning"
    else:
        severity = "pass"

    return ValidationResult(
        passed            = all_passed,
        checks            = checks,
        severity          = severity,
        pass_rate         = functional_pass_rate,
        functional_detail = functional_detail,
        file              = original_file.name,
    )


# ---------------------------------------------------------------------------
# Repository-level validator
# ---------------------------------------------------------------------------

def validate_repo(
    original_dir:   Path,
    refactored_dir: Path,
    test_dir:       Optional[Path] = None,
    run_functional: bool = True,
    inputs_per_func: int  = 6,
    func_timeout:   float = 5.0,
    report_dir:     Optional[Path] = None,
) -> list[dict]:
    """
    Validate every Python file in *original_dir* against its refactored
    counterpart in *refactored_dir*.

    File matching convention::

        original_dir/foo.py  ↔  refactored_dir/foo.refactored.py

    Returns
    -------
    A list of result dicts, one per original file::

        [
          {
            "file":      "order_service.py",
            "status":    "PASS",
            "pass_rate": 1.0,
            "severity":  "pass",
            "error":     None,
            "checks":    {"syntax": True, "ast_structure": True, …}
          },
          {
            "file":      "reg_tree.py",
            "status":    "FAIL",
            "pass_rate": 0.6,
            "severity":  "warning",
            "error":     "Mismatch in function output",
            "checks":    {"syntax": True, "ast_structure": True,
                          "functional": False}
          },
          …
        ]

    Files without a matching refactored counterpart are recorded with
    ``"status": "SKIP"``.  Validation crashes are caught and recorded as
    ``"status": "FAIL"`` with a traceback in ``"error"``.
    """
    original_dir   = Path(original_dir)
    refactored_dir = Path(refactored_dir)

    if report_dir is not None:
        Path(report_dir).mkdir(parents=True, exist_ok=True)

    py_files = sorted(original_dir.glob("*.py"))
    if not py_files:
        print(f"[validate_repo] No .py files found in {original_dir}")
        return []

    results: list[dict] = []

    for original_file in py_files:
        refactored_name = f"{original_file.stem}.refactored.py"
        refactored_file = refactored_dir / refactored_name

        print(f"\n{'='*60}")
        print(f"Validating: {original_file.name}")
        print(f"{'='*60}")

        # --- Missing refactored file ------------------------------------
        if not refactored_file.exists():
            print(f"  [SKIP] No refactored file: {refactored_name}")
            results.append({
                "file":      original_file.name,
                "status":    "SKIP",
                "pass_rate": None,
                "severity":  "skip",
                "error":     f"Refactored file not found: {refactored_name}",
                "checks":    {},
            })
            continue

        # --- Run validation (exception-safe) ----------------------------
        try:
            result = run_validation(
                original_file   = original_file,
                refactored_file = refactored_file,
                test_dir        = test_dir,
                run_functional  = run_functional,
                inputs_per_func = inputs_per_func,
                func_timeout    = func_timeout,
            )

            entry = {
                "file":      original_file.name,
                "status":    "PASS" if result.passed else "FAIL",
                "pass_rate": round(result.pass_rate, 4),
                "severity":  result.severity,
                "error":     _first_failure(result),
                "checks":    {k: v[0] for k, v in result.checks.items()},
            }

            # Optionally write per-file reports
            if report_dir is not None:
                stem = original_file.stem
                generate_report(
                    result,
                    Path(report_dir) / f"{stem}_report.txt",
                )
                generate_json_report(
                    result,
                    Path(report_dir) / f"{stem}_report.json",
                )

        except Exception as exc:  # noqa: BLE001
            tb = traceback.format_exc(limit=8)
            print(f"  [CRASH] Validation engine crashed: {exc}")
            entry = {
                "file":      original_file.name,
                "status":    "FAIL",
                "pass_rate": 0.0,
                "severity":  "error",
                "error":     f"Validator crashed: {type(exc).__name__}: {exc}\n{tb}",
                "checks":    {},
            }

        icon = "✓" if entry["status"] == "PASS" else ("−" if entry["status"] == "SKIP" else "✗")
        print(f"  [{icon}] {entry['status']}  pass_rate={entry['pass_rate']}")
        results.append(entry)

    # --- Summary -----------------------------------------------------------
    total  = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    skipped= sum(1 for r in results if r["status"] == "SKIP")
    failed = total - passed - skipped

    print(f"\n{'='*60}")
    print(f"REPO VALIDATION SUMMARY")
    print(f"  Total:   {total}  |  Passed: {passed}  |  "
          f"Failed: {failed}  |  Skipped: {skipped}")
    print(f"{'='*60}\n")

    # Write consolidated JSON report if requested
    if report_dir is not None:
        consolidated = Path(report_dir) / "validation_summary.json"
        consolidated.write_text(
            json.dumps(results, indent=2, default=str),
            encoding="utf-8",
        )
        print(f"→ Consolidated report: {consolidated}")

    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _first_failure(result: ValidationResult) -> Optional[str]:
    """Return the first failed check message, or None if all passed."""
    for name, (ok, msg) in result.checks.items():
        if not ok:
            return f"[{name}] {msg}"
    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Stage 4: Validate a refactored Python file or directory."
    )
    sub = parser.add_subparsers(dest="command")

    # --- Single-file mode ---
    single = sub.add_parser("file", help="Validate a single file pair")
    single.add_argument("--original",   required=True, help="Original .py file")
    single.add_argument("--refactored", required=True, help="Refactored .py file")
    single.add_argument("--tests",      help="Test directory (optional)")
    single.add_argument("--report",     default="validation_report.txt")
    single.add_argument("--json-report")
    single.add_argument("--no-functional", action="store_true")

    # --- Repo mode ---
    repo = sub.add_parser("repo", help="Validate an entire directory")
    repo.add_argument("--original-dir",   required=True)
    repo.add_argument("--refactored-dir", required=True)
    repo.add_argument("--tests")
    repo.add_argument("--report-dir", default="validation_reports")
    repo.add_argument("--no-functional", action="store_true")

    args = parser.parse_args()

    if args.command == "file":
        res = run_validation(
            Path(args.original),
            Path(args.refactored),
            Path(args.tests) if args.tests else None,
            run_functional=not args.no_functional,
        )
        generate_report(res, Path(args.report))
        if args.json_report:
            generate_json_report(res, Path(args.json_report))
        print_summary(res)
        raise SystemExit(0 if res.passed else 1)

    elif args.command == "repo":
        results = validate_repo(
            Path(args.original_dir),
            Path(args.refactored_dir),
            Path(args.tests) if args.tests else None,
            run_functional=not args.no_functional,
            report_dir=Path(args.report_dir),
        )
        raise SystemExit(0 if all(r["status"] in ("PASS", "SKIP") for r in results) else 1)

    else:
        parser.print_help()
