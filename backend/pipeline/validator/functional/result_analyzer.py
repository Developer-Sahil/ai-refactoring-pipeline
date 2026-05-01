# pipeline/validator/functional/result_analyzer.py
"""
Output comparison and result aggregation utilities.

``outputs_match`` performs a deep, type-aware equality check that handles:
- float NaN  (NaN == NaN → True, unlike Python default)
- float tolerance (configurable)
- nested containers (list, tuple, dict, set)
- NumPy arrays (optional dependency; gracefully skipped when absent)
- Mismatched numeric types  (int vs float)
"""
from __future__ import annotations

import inspect
import math
import re
from typing import Any


# ---------------------------------------------------------------------------
# Deep equality
# ---------------------------------------------------------------------------

def outputs_match(
    expected: Any,
    actual: Any,
    float_tol: float = 1e-9,
) -> bool:
    """Return ``True`` iff *expected* and *actual* are semantically equal."""

    # Fast path — same object
    if expected is actual:
        return True

    # Both None
    if expected is None and actual is None:
        return True
    if expected is None or actual is None:
        return False

    # Numeric cross-type (int vs float)
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return _floats_equal(float(expected), float(actual), float_tol)

    # Type mismatch — not equal
    if type(expected) is not type(actual):
        return False

    # Coroutines and Generators
    if inspect.iscoroutine(expected) and inspect.iscoroutine(actual):
        rep_e = re.sub(r" at 0x[0-9a-fA-F]+", "", repr(expected))
        rep_a = re.sub(r" at 0x[0-9a-fA-F]+", "", repr(actual))
        return rep_e == rep_a

    if inspect.isgenerator(expected) and inspect.isgenerator(actual):
        rep_e = re.sub(r" at 0x[0-9a-fA-F]+", "", repr(expected))
        rep_a = re.sub(r" at 0x[0-9a-fA-F]+", "", repr(actual))
        return rep_e == rep_a

    # Float
    if isinstance(expected, float):
        return _floats_equal(expected, actual, float_tol)

    # Exact equality types
    if isinstance(expected, (bool, int, str, bytes)):
        return expected == actual

    # Sequences (order matters)
    if isinstance(expected, (list, tuple)):
        if len(expected) != len(actual):
            return False
        return all(outputs_match(e, a, float_tol) for e, a in zip(expected, actual))

    # Mapping
    if isinstance(expected, dict):
        if set(expected.keys()) != set(actual.keys()):
            return False
        return all(outputs_match(expected[k], actual[k], float_tol) for k in expected)

    # Set
    if isinstance(expected, set):
        # Sets can contain floats; use approximate comparison if needed
        return expected == actual

    # NumPy arrays — optional dependency
    try:
        import numpy as np  # type: ignore[import]
        if isinstance(expected, np.ndarray) and isinstance(actual, np.ndarray):
            if expected.shape != actual.shape or expected.dtype != actual.dtype:
                return False
            if np.issubdtype(expected.dtype, np.floating):
                return bool(np.allclose(expected, actual, atol=float_tol, equal_nan=True))
            return bool(np.array_equal(expected, actual))
    except ImportError:
        pass

    # Generic fallback
    try:
        return bool(expected == actual)
    except Exception:
        return False


def _floats_equal(a: float, b: float, tol: float) -> bool:
    if math.isnan(a) and math.isnan(b):
        return True
    if math.isinf(a) or math.isinf(b):
        return a == b
    return math.isclose(a, b, rel_tol=tol, abs_tol=tol)


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def compute_aggregate(
    replay_results: list,       # list[ReplayResult] — avoid circular import
    property_results: dict | None = None,  # {func_name: [PropertyResult]}
) -> dict:
    """
    Combine ReplayResult list and optional PropertyResult dict into one
    structured summary dictionary.

    Returns
    -------
    {
      "total_tests":    int,
      "passed_tests":   int,
      "pass_rate":      float,          # 0.0 – 1.0
      "function_results": {
          "<func_name>": {
              "total":     int,
              "passed":    int,
              "pass_rate": float,
              "failures":  [str, …]     # capped at 5 entries
          }
      },
      "property_failures": [
          {"function": str, "property": str, "message": str}, …
      ]
    }
    """
    if not replay_results:
        return {
            "total_tests": 0,
            "passed_tests": 0,
            "pass_rate": 0.0,
            "function_results": {},
            "property_failures": [],
        }

    total  = sum(r.total  for r in replay_results)
    passed = sum(r.passed for r in replay_results)

    func_summary = {
        r.func_name: {
            "total":     r.total,
            "passed":    r.passed,
            "pass_rate": r.pass_rate,
            "failures":  r.failures[:5],  # cap to keep reports readable
        }
        for r in replay_results
    }

    prop_failures: list[dict] = []
    if property_results:
        for func_name, checks in property_results.items():
            for check in checks:
                if not check.passed:
                    prop_failures.append({
                        "function": func_name,
                        "property": check.property_name,
                        "message":  check.message,
                    })

    return {
        "total_tests":      total,
        "passed_tests":     passed,
        "pass_rate":        passed / total if total > 0 else 0.0,
        "function_results": func_summary,
        "property_failures": prop_failures,
    }
