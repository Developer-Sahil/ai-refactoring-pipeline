"""
cast.parsers.base_parser
~~~~~~~~~~~~~~~~~~~~~~~~
Abstract base class that every language-specific parser must implement.
Keeping the contract minimal makes adding new languages straightforward.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from cast.chunk_model import CodeChunk
from cast.file_reader import SourceFile


class BaseParser(ABC):
    """
    Contract for a cAST language parser.

    Subclasses must implement :meth:`extract_chunks`.
    They receive a fully-loaded :class:`~cast.file_reader.SourceFile`
    and must return an ordered sequence of :class:`~cast.chunk_model.CodeChunk`
    objects — one per logical structural unit found in the file.
    """

    # Human-readable name shown in logs / output metadata
    language: str = "unknown"

    @abstractmethod
    def extract_chunks(self, source: SourceFile) -> list[CodeChunk]:
        """
        Parse *source* and return a list of :class:`CodeChunk` objects.

        Rules
        -----
        * Chunks must be returned in source order (ascending start_line).
        * ``chunk_id`` values must be unique within the returned list.
        * The ``code`` field must be a verbatim slice of ``source.content``
          with original indentation and formatting intact.
        * No modifications to the original code are permitted.
        """

    # ------------------------------------------------------------------ #
    # Shared helpers available to every subclass                          #
    # ------------------------------------------------------------------ #

    @staticmethod
    def slice_lines(lines: list[str], start_line: int, end_line: int) -> str:
        """
        Return the verbatim source text for lines [*start_line* … *end_line*]
        (both 1-based, inclusive).
        """
        # lines list is 0-indexed; convert
        return "\n".join(lines[start_line - 1 : end_line])

    @staticmethod
    def make_chunk_id(index: int) -> str:
        """Return a deterministic chunk identifier string."""
        return f"chunk_{index}"
