# pipeline/validator/test_runner.py
import subprocess
import sys
from pathlib import Path

def run_pytest(source_file: Path, test_dir: Path = None) -> tuple[bool, str]:
    """
    Run pytest on the refactored source.
    Tests must already exist and import the source correctly.
    """
    if test_dir is None:
        test_dir = source_file.parent
    
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(test_dir), "-v"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    
    return result.returncode == 0, result.stdout + result.stderr