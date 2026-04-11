"""
Runs the validator test suite and writes clean output to a log file.
Usage: python run_tests.py
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parent.resolve()
OUT  = REPO / "tmp" / "test_results.txt"
OUT.parent.mkdir(exist_ok=True)

r = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/test_validator.py", "-v", "--tb=long", "--no-header"],
    capture_output=True,
    text=True,
    cwd=str(REPO),
    encoding="utf-8",
    errors="replace",
)

combined = r.stdout + ("\n--- STDERR ---\n" + r.stderr if r.stderr.strip() else "")
combined += f"\n\nEXIT CODE: {r.returncode}\n"

OUT.write_text(combined, encoding="utf-8")
print(combined)
print(f"\n[Saved to {OUT}]")
sys.exit(r.returncode)
