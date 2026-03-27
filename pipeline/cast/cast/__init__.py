"""
cAST — Code AST-based Chunking
================================
Stage 1 of the AI-powered code refactoring pipeline.

Quick start
-----------
>>> from cast.pipeline import run
>>> output_path = run("my_module.py", "chunks_output.json", verbose=True)
"""

from cast.pipeline import run

__all__ = ["run"]
__version__ = "1.0.0"
