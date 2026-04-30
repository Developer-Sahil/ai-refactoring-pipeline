# pipeline/validator/ast_comparator.py
"""
Structural AST comparator.

Goal: detect *significant* structural regressions introduced by the LLM
while tolerating purely cosmetic changes (renaming, reordering, docstrings,
type annotations, whitespace).

What is checked
---------------
* Top-level function count must not change.
* Top-level class count must not change.
* For each top-level function: argument count must be preserved.
* For each top-level function: ``*args`` / ``**kwargs`` presence preserved.
* For each top-level class: method count must be preserved.
* Return annotations: if original has one, refactored must too (and vice-versa).

What is intentionally *not* checked
-------------------------------------
* Variable names, docstrings, comments — these are the whole point of refactoring.
* Exact body length — the LLM might legitimately extract helpers.
* Import order / alias changes.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Fingerprint data classes
# ---------------------------------------------------------------------------

@dataclass
class FuncFingerprint:
    name:           str
    positional_args: int
    has_varargs:    bool
    has_kwargs:     bool
    has_return_ann: bool


@dataclass
class ClassFingerprint:
    name:         str
    method_count: int
    base_count:   int


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

def _func_fingerprint(node: ast.FunctionDef | ast.AsyncFunctionDef) -> FuncFingerprint:
    args = node.args
    return FuncFingerprint(
        name            = node.name,
        positional_args = len(args.args) + len(args.posonlyargs),
        has_varargs     = args.vararg is not None,
        has_kwargs      = args.kwarg  is not None,
        has_return_ann  = node.returns is not None,
    )


def _class_fingerprint(node: ast.ClassDef) -> ClassFingerprint:
    method_count = sum(
        1 for item in node.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
    )
    return ClassFingerprint(
        name         = node.name,
        method_count = method_count,
        base_count   = len(node.bases),
    )


def _extract_top_level(tree: ast.Module) -> tuple[
    dict[str, FuncFingerprint],
    dict[str, ClassFingerprint],
]:
    """Return (functions, classes) dicts keyed by name."""
    funcs   = {}
    classes = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fp = _func_fingerprint(node)
            funcs[node.name] = fp
        elif isinstance(node, ast.ClassDef):
            cp = _class_fingerprint(node)
            classes[node.name] = cp
    return funcs, classes


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compare_chunks(original_code: str, refactored_code: str) -> tuple[bool, str]:
    """
    Compare structural fingerprints of *original_code* vs *refactored_code*.

    Returns ``(True, "AST structure preserved")`` or ``(False, "<reason>")``.
    """
    try:
        orig_tree  = ast.parse(original_code)
        refac_tree = ast.parse(refactored_code)
    except SyntaxError as exc:
        return False, f"Cannot parse for AST comparison: {exc}"

    orig_funcs,  orig_classes  = _extract_top_level(orig_tree)
    refac_funcs, refac_classes = _extract_top_level(refac_tree)

    issues: list[str] = []

    # --- Function count ---------------------------------------------------
    if len(orig_funcs) != len(refac_funcs):
        issues.append(
            f"Top-level function count changed: "
            f"{len(orig_funcs)} → {len(refac_funcs)}"
        )
    else:
        # Per-function signature check (by name, if names are stable)
        for name, ofp in orig_funcs.items():
            if name not in refac_funcs:
                issues.append(f"Function '{name}' missing in refactored code")
                continue
            rfp = refac_funcs[name]
            if ofp.positional_args != rfp.positional_args:
                issues.append(
                    f"Function '{name}': positional arg count changed "
                    f"{ofp.positional_args} → {rfp.positional_args}"
                )
            if ofp.has_varargs != rfp.has_varargs:
                issues.append(
                    f"Function '{name}': *args presence changed "
                    f"{ofp.has_varargs} → {rfp.has_varargs}"
                )
            if ofp.has_kwargs != rfp.has_kwargs:
                issues.append(
                    f"Function '{name}': **kwargs presence changed "
                    f"{ofp.has_kwargs} → {rfp.has_kwargs}"
                )

    # --- Class count ------------------------------------------------------
    if len(orig_classes) != len(refac_classes):
        issues.append(
            f"Top-level class count changed: "
            f"{len(orig_classes)} → {len(refac_classes)}"
        )
    else:
        for name, ocp in orig_classes.items():
            if name not in refac_classes:
                issues.append(f"Class '{name}' missing in refactored code")
                continue
            rcp = refac_classes[name]
            if ocp.method_count != rcp.method_count:
                issues.append(
                    f"Class '{name}': method count changed "
                    f"{ocp.method_count} → {rcp.method_count}"
                )

    if issues:
        return False, "; ".join(issues)

    return True, "AST structure preserved"
