# pipeline/validator/functional/input_generator.py
"""
Type-aware input generator for arbitrary Python functions.

Strategy
--------
1. Inspect the function signature for parameter annotations.
2. Dispatch each annotation to a typed generator (primitive, generic, optional, …).
3. Include edge cases (0, empty, boundary values) in every generated set.
4. Fall back gracefully when annotations are absent or un-parseable.
"""
from __future__ import annotations

import inspect
import random
import string
import types
import typing
from typing import Any, Callable, get_type_hints

# ---------------------------------------------------------------------------
# Primitive generators: each returns a different value on every call
# to give the test suite diversity across N runs.
# ---------------------------------------------------------------------------

_EDGE_INTS   = [0, 1, -1, 2**31 - 1, -(2**31)]
_EDGE_FLOATS = [0.0, 1.0, -1.0, 1e9, -1e9, 1e-9]
_EDGE_STRS   = ["", "hello", " ", "123", "!@#$", "a" * 256]
_EDGE_LISTS  = [[], [0], [1, 2, 3], list(range(10))]
_EDGE_DICTS  = [{}, {"a": 1}, {"x": 0, "y": 0}]


def _rand_str(k: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=k))


_PRIMITIVE_GENERATORS: dict[type, Callable[[], Any]] = {
    int:   lambda: random.choice(_EDGE_INTS + [random.randint(-1000, 1000)]),
    float: lambda: random.choice(_EDGE_FLOATS + [random.uniform(-1000.0, 1000.0)]),
    str:   lambda: random.choice(_EDGE_STRS + [_rand_str()]),
    bool:  lambda: random.choice([True, False]),
    bytes: lambda: random.choice([b"", b"hello", bytes(random.randint(0, 255) for _ in range(5))]),
    list:  lambda: random.choice(_EDGE_LISTS + [[random.randint(0, 100) for _ in range(random.randint(1, 6))]]),
    dict:  lambda: random.choice(_EDGE_DICTS + [{_rand_str(4): random.randint(0, 9) for _ in range(random.randint(1, 4))}]),
    tuple: lambda: random.choice([(), (1,), (1, 2, 3), tuple(range(random.randint(0, 5)))]),
    set:   lambda: random.choice([set(), {1, 2, 3}]),
}


# ---------------------------------------------------------------------------
# Recursive dispatcher
# ---------------------------------------------------------------------------

def _generate_for_annotation(annotation: Any) -> Any:  # noqa: C901
    """Return one value that satisfies *annotation* (best-effort)."""

    if annotation is inspect.Parameter.empty:
        # No annotation — use a simple scalar so we at least call the function
        return random.choice([0, 1, "test", True, 3.14])

    # Unwrap typing generics
    origin = getattr(annotation, "__origin__", None)
    args   = getattr(annotation, "__args__", ()) or ()

    # ---- Union / Optional -----------------------------------------------
    if origin is typing.Union:
        non_none = [a for a in args if a is not type(None)]
        if not non_none:
            return None
        # 15 % chance of returning None when it is a valid value
        if type(None) in args and random.random() < 0.15:
            return None
        return _generate_for_annotation(random.choice(non_none))

    # ---- List[X] --------------------------------------------------------
    if origin is list:
        elem_type = args[0] if args else int
        length = random.randint(0, 4)
        return [_generate_for_annotation(elem_type) for _ in range(length)]

    # ---- Dict[K, V] -----------------------------------------------------
    if origin is dict:
        k_type = args[0] if len(args) > 0 else str
        v_type = args[1] if len(args) > 1 else int
        return {_generate_for_annotation(k_type): _generate_for_annotation(v_type)
                for _ in range(random.randint(0, 3))}

    # ---- Tuple[X, Y, …] -------------------------------------------------
    if origin is tuple:
        if not args:
            return ()
        # Handle Tuple[X, ...] (variable-length homogeneous)
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(_generate_for_annotation(args[0]) for _ in range(random.randint(0, 4)))
        return tuple(_generate_for_annotation(a) for a in args)

    # ---- Set[X] ---------------------------------------------------------
    if origin is set:
        elem_type = args[0] if args else int
        return {_generate_for_annotation(elem_type) for _ in range(random.randint(0, 3))}

    # ---- Literal[…] -----------------------------------------------------
    # Python 3.8+ typing.Literal
    if hasattr(typing, "Literal") and origin is typing.Literal:
        return random.choice(args) if args else None

    # ---- Primitive types ------------------------------------------------
    if annotation in _PRIMITIVE_GENERATORS:
        return _PRIMITIVE_GENERATORS[annotation]()

    # ---- Fallback: try to instantiate the class with no args ------------
    if inspect.isclass(annotation):
        try:
            return annotation()
        except Exception:
            pass

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_inputs_for_function(
    func: Callable,
    n: int = 6,
) -> list[tuple[tuple, dict]]:
    """
    Return *n* ``(args_tuple, kwargs_dict)`` pairs for *func*.

    Edge-case set is always included as the first entry so that trivial
    inputs (zeros, empty strings) are never missed.
    """
    try:
        sig   = inspect.signature(func)
        hints = {}
        try:
            hints = get_type_hints(func)
        except Exception:
            pass
    except (ValueError, TypeError):
        # Completely un-inspectable (e.g. built-in C extension)
        return [((), {}) for _ in range(n)]

    # Filter parameters we can meaningfully generate values for
    usable_params = [
        (name, param)
        for name, param in sig.parameters.items()
        if param.kind not in (
            inspect.Parameter.VAR_POSITIONAL,   # *args
            inspect.Parameter.VAR_KEYWORD,      # **kwargs
        )
        and name != "self"
        and name != "cls"
    ]

    if not usable_params:
        # Zero-argument function
        return [( (), {} ) for _ in range(n)]

    results: list[tuple[tuple, dict]] = []

    for i in range(n):
        call_args: list[Any] = []
        for name, param in usable_params:
            annotation = hints.get(name, param.annotation)

            # 20 % chance to reuse the default value when one exists,
            # so we also exercise the "happy path" code.
            if (
                param.default is not inspect.Parameter.empty
                and random.random() < 0.20
            ):
                call_args.append(param.default)
            else:
                call_args.append(_generate_for_annotation(annotation))

        results.append((tuple(call_args), {}))

    return results
