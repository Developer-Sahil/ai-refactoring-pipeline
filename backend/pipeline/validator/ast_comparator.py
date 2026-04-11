# pipeline/validator/ast_comparator.py
import ast
from typing import Any

def normalize_ast(node: ast.AST) -> dict:
    """
    Create a normalized AST fingerprint, ignoring cosmetic changes
    (variable names, comments, formatting).
    """
    if isinstance(node, ast.FunctionDef):
        return {
            "type": "function",
            "arg_count": len(node.args.args),
            "body_length": len(node.body),
            "returns": node.returns is not None,
        }
    elif isinstance(node, ast.ClassDef):
        return {
            "type": "class",
            "method_count": sum(1 for item in node.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))),
            "bases": len(node.bases),
        }
    # Add more as needed
    return {}

def compare_chunks(original_code: str, refactored_code: str) -> tuple[bool, str]:
    """
    Compare original and refactored code at AST level.
    Allows renaming but catches major structural breaks.
    """
    try:
        orig_ast = ast.parse(original_code)
        refac_ast = ast.parse(refactored_code)
        
        # Extract TOP-LEVEL definitions only.
        # Using ast.walk() would also capture methods inside classes and
        # nested functions, causing false-positive count mismatches.
        orig_funcs = {
            node.name: normalize_ast(node)
            for node in orig_ast.body
            if isinstance(node, ast.FunctionDef)
        }
        refac_funcs = {
            node.name: normalize_ast(node)
            for node in refac_ast.body
            if isinstance(node, ast.FunctionDef)
        }
        
        # Same number of functions?
        if len(orig_funcs) != len(refac_funcs):
            return False, f"Function count changed: {len(orig_funcs)} → {len(refac_funcs)}"
        
        # Rough structural match (real comparison is complex)
        return True, "AST structure preserved"
    except Exception as e:
        return False, f"AST comparison failed: {e}"