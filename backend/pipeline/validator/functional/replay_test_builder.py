# pipeline/validator/functional/replay_test_builder.py
"""
Replay-based behavioral equivalence testing.

Phase 1 — Capture
    Run every function in the original module with generated inputs and
    record the (args, kwargs, output / exception) triples.

Phase 2 — Replay
    Feed the exact same inputs to the refactored module and compare.

Comparison rules
----------------
Both succeed     → outputs must be semantically equal (via result_analyzer)
Both raise        → exception *class names* must match
One raises, one doesn't → FAIL (behavioral contract broken)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import ModuleType
from typing import Any, Optional

from .behavior_capture import extract_callable_functions
from .input_generator import generate_inputs_for_function
from .test_executor import execute_with_timeout
from .result_analyzer import outputs_match


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class TestCase:
    """A single captured execution of *func_name* with known expected output."""
    func_name:          str
    args:               tuple
    kwargs:             dict
    expected_output:    Any
    expected_exc_type:  Optional[str]   # e.g. "ValueError", or None
    orig_succeeded:     bool            # False if original raised


@dataclass
class ReplayResult:
    """Aggregated replay outcome for one function."""
    func_name: str
    total:     int
    passed:    int
    failures:  list[str] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total > 0 else 0.0

    @property
    def ok(self) -> bool:
        return self.passed == self.total


# ---------------------------------------------------------------------------
# Phase 1: Capture
# ---------------------------------------------------------------------------

def capture_behavior(
    original_module: ModuleType,
    inputs_per_func: int = 6,
    timeout:         float = 5.0,
) -> dict[str, list[TestCase]]:
    """
    Execute each public function in *original_module* and record results.

    Returns ``{func_name: [TestCase, …]}``.
    """
    funcs     = extract_callable_functions(original_module)
    test_bank: dict[str, list[TestCase]] = {}

    for name, func in funcs.items():
        cases:  list[TestCase] = []
        inputs = generate_inputs_for_function(func, n=inputs_per_func)

        for args, kwargs in inputs:
            success, result, error = execute_with_timeout(func, args, kwargs, timeout)

            # Extract just the exception class name (before the first colon)
            exc_type: Optional[str] = None
            if error:
                exc_type = error.split(":")[0].split("\\n")[0].strip()

            cases.append(TestCase(
                func_name         = name,
                args              = args,
                kwargs            = kwargs,
                expected_output   = result,
                expected_exc_type = exc_type,
                orig_succeeded    = success,
            ))

        if cases:
            test_bank[name] = cases

    return test_bank


# ---------------------------------------------------------------------------
# Phase 2: Replay
# ---------------------------------------------------------------------------

def replay_against_refactored(
    refactored_module: ModuleType,
    test_bank:         dict[str, list[TestCase]],
    timeout:           float = 5.0,
) -> list[ReplayResult]:
    """
    Replay every captured TestCase against *refactored_module*.

    Returns a list of ``ReplayResult``, one per function.
    """
    refac_funcs = extract_callable_functions(refactored_module)
    results: list[ReplayResult] = []

    for func_name, cases in test_bank.items():
        if func_name not in refac_funcs:
            results.append(ReplayResult(
                func_name = func_name,
                total     = len(cases),
                passed    = 0,
                failures  = [
                    f"Function '{func_name}' missing in refactored module — "
                    "was it renamed or removed?"
                ],
            ))
            continue

        refac_func = refac_funcs[func_name]
        passed     = 0
        failures:  list[str] = []

        for case in cases:
            r_success, r_result, r_error = execute_with_timeout(
                refac_func, case.args, case.kwargs, timeout
            )

            # --- Both succeeded -------------------------------------------
            if case.orig_succeeded and r_success:
                if outputs_match(case.expected_output, r_result):
                    passed += 1
                else:
                    failures.append(
                        f"args={_fmt(case.args)}: "
                        f"expected={_fmt(case.expected_output)!r}, "
                        f"got={_fmt(r_result)!r}"
                    )

            # --- Both raised ----------------------------------------------
            elif not case.orig_succeeded and not r_success:
                orig_exc  = (case.expected_exc_type or "").strip()
                refac_exc = (r_error or "").split(":")[0].split("\\n")[0].strip()
                if orig_exc == refac_exc:
                    passed += 1
                else:
                    failures.append(
                        f"args={_fmt(case.args)}: "
                        f"orig raised {orig_exc!r}, "
                        f"refactored raised {refac_exc!r}"
                    )

            # --- Divergence (one succeeded, one failed) -------------------
            else:
                side   = "original" if case.orig_succeeded else "refactored"
                detail = r_error if not r_success else "no error"
                failures.append(
                    f"args={_fmt(case.args)}: "
                    f"{side} returned normally, other raised — "
                    f"refactored error: {detail}"
                )

        results.append(ReplayResult(
            func_name = func_name,
            total     = len(cases),
            passed    = passed,
            failures  = failures,
        ))

    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt(value: Any, max_len: int = 80) -> str:
    """Truncate repr for human-readable failure messages."""
    s = repr(value)
    return s if len(s) <= max_len else s[:max_len] + "…"
