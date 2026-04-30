# pipeline/validator/functional/property_test_builder.py
"""
Property-based validation checks.

Unlike replay testing (which asserts exact output equality), these checks
validate higher-level *invariants* that any correct implementation must
satisfy — regardless of internal refactoring decisions.

Implemented properties
----------------------
determinism        The refactored function returns the same result when
                   called twice with identical inputs (catches non-pure
                   implementations that accidentally introduced randomness
                   or mutable-default-argument bugs).

type_stability     The return type of the refactored function matches the
                   original for the same inputs (catches accidental
                   int→float, list→tuple, etc. promotions).

exception_contract If the original raises for a given input, the refactored
                   version must also raise (the error contract is part of the
                   public API).

idempotence        (Optional / best-effort) If f(f(x)) == f(x) for the
                   original, it should hold for the refactored version too.
                   Only tested on functions that appear to be idempotent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import ModuleType
from typing import Any, Callable

from .behavior_capture import extract_callable_functions
from .input_generator import generate_inputs_for_function
from .test_executor import execute_with_timeout
from .result_analyzer import outputs_match


# ---------------------------------------------------------------------------
# Data structure
# ---------------------------------------------------------------------------

@dataclass
class PropertyResult:
    property_name: str
    func_name:     str
    passed:        bool
    message:       str = ""


# ---------------------------------------------------------------------------
# Individual property checks
# ---------------------------------------------------------------------------

def check_determinism(
    refac_func: Callable,
    func_name:  str,
    n:          int   = 5,
    timeout:    float = 5.0,
) -> list[PropertyResult]:
    """
    Call *refac_func* twice with the same inputs; results must be equal.
    Non-determinism after refactoring is a strong indicator of a bug
    (mutable default, missing seed, shared state, etc.).
    """
    results: list[PropertyResult] = []

    for args, kwargs in generate_inputs_for_function(refac_func, n=n):
        s1, r1, _ = execute_with_timeout(refac_func, args, kwargs, timeout)
        s2, r2, _ = execute_with_timeout(refac_func, args, kwargs, timeout)

        if not s1 or not s2:
            # Cannot assess determinism if the function errors
            continue

        if outputs_match(r1, r2):
            results.append(PropertyResult("determinism", func_name, True))
        else:
            results.append(PropertyResult(
                "determinism", func_name, False,
                f"Non-deterministic: args={_fmt(args)} → {_fmt(r1)!r} ≠ {_fmt(r2)!r}",
            ))

    return results


def check_type_stability(
    orig_func:  Callable,
    refac_func: Callable,
    func_name:  str,
    n:          int   = 5,
    timeout:    float = 5.0,
) -> list[PropertyResult]:
    """
    The concrete type of the return value must match between original and
    refactored for the same inputs.
    """
    results: list[PropertyResult] = []

    for args, kwargs in generate_inputs_for_function(orig_func, n=n):
        so, ro, _ = execute_with_timeout(orig_func,  args, kwargs, timeout)
        sr, rr, _ = execute_with_timeout(refac_func, args, kwargs, timeout)

        if not so or not sr:
            continue

        orig_type  = type(ro).__name__
        refac_type = type(rr).__name__

        if orig_type == refac_type:
            results.append(PropertyResult("type_stability", func_name, True))
        else:
            results.append(PropertyResult(
                "type_stability", func_name, False,
                f"Return-type changed: orig={orig_type}, refactored={refac_type} "
                f"for args={_fmt(args)}",
            ))

    return results


def check_exception_contract(
    orig_func:  Callable,
    refac_func: Callable,
    func_name:  str,
    n:          int   = 5,
    timeout:    float = 5.0,
) -> list[PropertyResult]:
    """
    If the original raises for given inputs, the refactored version must too.
    The *type* of exception must also match (the error API is a contract).
    """
    results: list[PropertyResult] = []

    for args, kwargs in generate_inputs_for_function(orig_func, n=n):
        so, _, eo = execute_with_timeout(orig_func,  args, kwargs, timeout)
        sr, _, er = execute_with_timeout(refac_func, args, kwargs, timeout)

        if so:
            # Original succeeded — exception contract not applicable here
            continue

        orig_exc  = (eo or "").split(":")[0].strip()

        if not sr:
            refac_exc = (er or "").split(":")[0].strip()
            if orig_exc == refac_exc:
                results.append(PropertyResult("exception_contract", func_name, True))
            else:
                results.append(PropertyResult(
                    "exception_contract", func_name, False,
                    f"Exception type changed: orig={orig_exc!r}, "
                    f"refactored={refac_exc!r} for args={_fmt(args)}",
                ))
        else:
            results.append(PropertyResult(
                "exception_contract", func_name, False,
                f"Original raised {orig_exc!r} but refactored succeeded "
                f"for args={_fmt(args)}",
            ))

    return results


def check_idempotence(
    orig_func:  Callable,
    refac_func: Callable,
    func_name:  str,
    n:          int   = 3,
    timeout:    float = 5.0,
) -> list[PropertyResult]:
    """
    Best-effort: check whether f(f(x)) == f(x) holds for both versions.

    This is *only* reported as a failure if the original is idempotent but
    the refactored version is not — not if neither is idempotent.
    """
    results: list[PropertyResult] = []

    for args, kwargs in generate_inputs_for_function(orig_func, n=n):
        # Original: f(x)
        so1, ro1, _ = execute_with_timeout(orig_func, args, kwargs, timeout)
        if not so1:
            continue
        # Original: f(f(x)) — apply the function again to its own result
        try:
            second_args = (ro1,) if not isinstance(ro1, tuple) else ro1
            so2, ro2, _ = execute_with_timeout(orig_func, second_args, {}, timeout)
        except Exception:
            continue

        orig_is_idempotent = so2 and outputs_match(ro1, ro2)

        if not orig_is_idempotent:
            # Original is not idempotent; property does not apply
            continue

        # Refactored: f(x)
        sr1, rr1, _ = execute_with_timeout(refac_func, args, kwargs, timeout)
        if not sr1:
            continue
        try:
            second_args_r = (rr1,) if not isinstance(rr1, tuple) else rr1
            sr2, rr2, _  = execute_with_timeout(refac_func, second_args_r, {}, timeout)
        except Exception:
            continue

        refac_is_idempotent = sr2 and outputs_match(rr1, rr2)

        if refac_is_idempotent:
            results.append(PropertyResult("idempotence", func_name, True))
        else:
            results.append(PropertyResult(
                "idempotence", func_name, False,
                f"Original is idempotent but refactored is not for args={_fmt(args)}",
            ))

    return results


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_all_property_checks(
    original_module:   ModuleType,
    refactored_module: ModuleType,
    n:                 int   = 5,
    timeout:           float = 5.0,
    check_idempotence_flag: bool = False,
) -> dict[str, list[PropertyResult]]:
    """
    Run all property checks for every function shared between the two modules.

    Returns ``{func_name: [PropertyResult, …]}``.
    """
    orig_funcs  = extract_callable_functions(original_module)
    refac_funcs = extract_callable_functions(refactored_module)
    shared      = set(orig_funcs) & set(refac_funcs)

    all_results: dict[str, list[PropertyResult]] = {}

    for name in sorted(shared):
        of = orig_funcs[name]
        rf = refac_funcs[name]

        checks: list[PropertyResult] = []
        checks.extend(check_determinism(rf, name, n, timeout))
        checks.extend(check_type_stability(of, rf, name, n, timeout))
        checks.extend(check_exception_contract(of, rf, name, n, timeout))
        if check_idempotence_flag:
            checks.extend(check_idempotence(of, rf, name, n=3, timeout=timeout))

        all_results[name] = checks

    return all_results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt(value: Any, max_len: int = 60) -> str:
    s = repr(value)
    return s if len(s) <= max_len else s[:max_len] + "…"
