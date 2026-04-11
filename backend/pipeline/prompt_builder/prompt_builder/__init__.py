"""
prompt_builder
~~~~~~~~~~~~~~
Stage 2 of the AI refactoring pipeline.

Reads cAST chunk output and generates structured LLM refactoring prompts.

Quick start::

    from prompt_builder.build_prompts import run
    run("cast/chunks_output.json", "outputs/prompts.json", verbose=True)
"""

from prompt_builder.build_prompts import run

__all__ = ["run"]
__version__ = "1.0.0"
