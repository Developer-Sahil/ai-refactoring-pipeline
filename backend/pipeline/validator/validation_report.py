# pipeline/validator/validation_report.py
"""
Stage 4 — Validation Report Generator.

Renders human-readable text and machine-readable JSON reports from a
``ValidationResult``.  Compatible with both the legacy NamedTuple and the
new dataclass form of ValidationResult.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Only imported for type hints; avoid circular import at runtime.
    from run_validation import ValidationResult  # type: ignore[import]


# ---------------------------------------------------------------------------
# Human-readable text report
# ---------------------------------------------------------------------------

def generate_report(result: "ValidationResult", output_path: Path) -> None:
    """
    Write a UTF-8 human-readable report to *output_path*.
    """
    lines: list[str] = []
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    file_label = getattr(result, "file", "—")

    lines += [
        "=" * 64,
        "  CODE VALIDATION REPORT",
        f"  File      : {file_label}",
        f"  Generated : {now}",
        "=" * 64,
        f"\n  Overall Status : {'✓ PASS' if result.passed else '✗ FAIL'}",
        f"  Severity       : {result.severity.upper()}",
    ]

    # Pass rate (only meaningful if functional tests ran)
    pass_rate = getattr(result, "pass_rate", None)
    if pass_rate is not None:
        lines.append(f"  Pass Rate      : {pass_rate:.1%}")

    lines += ["", "-" * 64, "  CHECK RESULTS", "-" * 64]

    for check_name, (ok, message) in result.checks.items():
        icon = "✓" if ok else "✗"
        # Truncate long messages (e.g. full flake8 output) to 120 chars
        short_msg = message[:120] + "…" if len(message) > 120 else message
        lines.append(f"  {icon}  {check_name:<22s}  │  {short_msg}")

    # Per-function breakdown (if functional testing ran)
    fd = getattr(result, "functional_detail", {})
    func_results = fd.get("function_results", {})
    if func_results:
        lines += ["", "-" * 64, "  PER-FUNCTION BREAKDOWN", "-" * 64]
        for fname, info in func_results.items():
            rate = info.get("pass_rate", 0)
            total = info.get("total", 0)
            passed = info.get("passed", 0)
            icon = "✓" if rate == 1.0 else "✗"
            lines.append(
                f"  {icon}  {fname:<30s}  {passed}/{total} ({rate:.0%})"
            )
            for fail in info.get("failures", [])[:3]:
                lines.append(f"       ↳ {fail[:100]}")

    prop_failures = fd.get("property_failures", [])
    if prop_failures:
        lines += ["", "-" * 64, "  PROPERTY VIOLATIONS", "-" * 64]
        for pf in prop_failures[:10]:
            lines.append(
                f"  ✗  [{pf['property']}] {pf['function']}: {pf['message'][:100]}"
            )

    lines += ["", "=" * 64]

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"→ Report written to: {output_path}")


# ---------------------------------------------------------------------------
# JSON report
# ---------------------------------------------------------------------------

def generate_json_report(result: "ValidationResult", output_path: Path) -> None:
    """
    Write a JSON-formatted report to *output_path*.
    """
    payload: dict = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "file":      getattr(result, "file", None),
        "passed":    result.passed,
        "severity":  result.severity,
        "pass_rate": getattr(result, "pass_rate", None),
        "checks": {
            name: {"passed": ok, "message": msg}
            for name, (ok, msg) in result.checks.items()
        },
    }

    fd = getattr(result, "functional_detail", {})
    if fd:
        payload["functional_detail"] = fd

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"→ JSON report written to: {output_path}")


# ---------------------------------------------------------------------------
# CLI helper
# ---------------------------------------------------------------------------

def print_summary(result: "ValidationResult") -> None:
    """Print a one-line summary to stdout."""
    icon   = "✓" if result.passed else "✗"
    failed = [name for name, (ok, _) in result.checks.items() if not ok]
    detail = f"  (failed: {', '.join(failed)})" if failed else ""
    rate   = getattr(result, "pass_rate", None)
    rate_s = f"  pass_rate={rate:.1%}" if rate is not None else ""
    print(
        f"\n{icon} Validation {'PASSED' if result.passed else 'FAILED'} "
        f"[{result.severity.upper()}]{rate_s}{detail}\n"
    )
