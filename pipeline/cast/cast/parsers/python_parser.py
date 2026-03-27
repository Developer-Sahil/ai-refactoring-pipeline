"""
cast.parsers.python_parser
~~~~~~~~~~~~~~~~~~~~~~~~~~
Python parser using the stdlib ``ast`` module.

Extracts:
  * Module-level functions  (``function``)
  * Async module-level functions (``async_function``)
  * Top-level classes  (``class``)
  * Methods inside classes  (``method``)
  * Async methods inside classes (``async_method``)

The parser uses ``ast.get_source_segment`` logic via line numbers to
extract exact verbatim code slices — no reformatting is applied.
"""

from __future__ import annotations

import ast
import textwrap
from typing import Optional

from cast.chunk_model import CodeChunk
from cast.file_reader import SourceFile
from cast.parsers.base_parser import BaseParser


class PythonParser(BaseParser):
    language = "python"

    def extract_chunks(self, source: SourceFile) -> list[CodeChunk]:
        try:
            tree = ast.parse(source.content)
        except SyntaxError as exc:
            raise ValueError(f"Python syntax error in {source.path}: {exc}") from exc

        chunks: list[CodeChunk] = []
        counter = 1

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Emit the class itself
                chunk = self._node_to_chunk(node, "class", source, counter)
                chunks.append(chunk)
                counter += 1

                # Emit each method inside the class
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        mtype = "async_method" if isinstance(item, ast.AsyncFunctionDef) else "method"
                        method_chunk = self._node_to_chunk(
                            item, mtype, source, counter,
                            metadata={"parent_class": node.name}
                        )
                        chunks.append(method_chunk)
                        counter += 1

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Only emit top-level functions (not methods — those are
                # handled above inside their class)
                if self._is_top_level(node, tree):
                    ftype = "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function"
                    chunk = self._node_to_chunk(node, ftype, source, counter)
                    chunks.append(chunk)
                    counter += 1

        # Sort by start_line before returning
        chunks.sort(key=lambda c: c.start_line)

        # Re-number after sort to keep IDs sequential in file order
        for i, chunk in enumerate(chunks, start=1):
            chunk.chunk_id = self.make_chunk_id(i)

        return chunks

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _node_to_chunk(
        self,
        node: ast.AST,
        chunk_type: str,
        source: SourceFile,
        index: int,
        metadata: Optional[dict] = None,
    ) -> CodeChunk:
        start_line: int = node.lineno          # type: ignore[attr-defined]
        end_line: int   = node.end_lineno      # type: ignore[attr-defined]

        # Include any decorators that appear before the def/class line
        if hasattr(node, "decorator_list") and node.decorator_list:  # type: ignore[attr-defined]
            start_line = min(d.lineno for d in node.decorator_list)  # type: ignore[attr-defined]

        code = self.slice_lines(source.lines, start_line, end_line)

        return CodeChunk(
            chunk_id=self.make_chunk_id(index),
            type=chunk_type,
            name=getattr(node, "name", None),
            start_line=start_line,
            end_line=end_line,
            code=code,
            metadata=metadata or {},
        )

    @staticmethod
    def _is_top_level(
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        tree: ast.Module,
    ) -> bool:
        """Return True if *node* is a direct child of the module (not inside a class)."""
        for parent in ast.walk(tree):
            if isinstance(parent, ast.ClassDef):
                for child in ast.walk(parent):
                    if child is node:
                        return False
        return True
