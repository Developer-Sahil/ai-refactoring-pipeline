# pipeline/validator/validation_report.py
"""
Stage 4 — Validation Report Generator.
Renders a human-readable and machine-readable summary of the ValidationResult.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

# ValidationResult is defined in run_validation; use a string annotation to
# avoid a circular / cross-module import at runtime.
# The type is only used for IDE hints and mypy, not at runtime.


# ---------------------------------------------------------------------------
# Human-readable text report
# ---------------------------------------------------------------------------

def generate_report(result: "ValidationResult", output_path: Path) -> None:
    """
    Write a human-readable validation report to *output_path*.

    The file is UTF-8 encoded so that Unicode status glyphs (✓ ✗ →) render
    correctly on all platforms, including Windows.
    """
    lines: list[str] = []
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines.append("=" * 60)
    lines.append("CODE VALIDATION REPORT")
    lines.append(f"Generated : {now}")
    lines.append("=" * 60)
    lines.append(f"\nOverall Status : {'✓ PASS' if result.passed else '✗ FAIL'}")
    lines.append(f"Severity       : {result.severity.upper()}\n")
    lines.append("-" * 60)

    for check_name, (passed, message) in result.checks.items():
        status = "✓" if passed else "✗"
        lines.append(f"  {status}  {check_name:<20s}  |  {message}")

    lines.append("\n" + "=" * 60)

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"→ Report written to: {output_path}")


# ---------------------------------------------------------------------------
# Machine-readable JSON report (optional, for CI integration)
# ---------------------------------------------------------------------------

def generate_json_report(result: "ValidationResult", output_path: Path) -> None:
    """
    Write a JSON-formatted validation report to *output_path*.
    Useful for downstream CI tools that parse structured output.
    """
    payload = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "passed": result.passed,
        "severity": result.severity,
        "checks": {
            name: {"passed": passed, "message": msg}
            for name, (passed, msg) in result.checks.items()
        },
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"→ JSON report written to: {output_path}")


# ---------------------------------------------------------------------------
# CLI helper: pretty-print to stdout
# ---------------------------------------------------------------------------

def print_summary(result: "ValidationResult") -> None:
    """Print a compact one-line summary suitable for terminal output."""
    icon = "✓" if result.passed else "✗"
    failed = [name for name, (ok, _) in result.checks.items() if not ok]
    detail = f"  (failed: {', '.join(failed)})" if failed else ""
    print(f"\n{icon} Validation {'PASSED' if result.passed else 'FAILED'} "
          f"[{result.severity.upper()}]{detail}\n")
