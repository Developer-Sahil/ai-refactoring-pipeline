# pipeline/validator/syntax_validator.py
import ast
from pathlib import Path

def validate_python_syntax(file_path: Path) -> tuple[bool, str]:
    """
    Parse Python file to check for syntax errors.
    Returns (is_valid, error_message).
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            ast.parse(f.read())
        return True, "Syntax OK"
    except SyntaxError as e:
        return False, f"Syntax Error at line {e.lineno}: {e.msg}"
    except Exception as e:
        return False, str(e)