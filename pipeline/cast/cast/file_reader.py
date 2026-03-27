"""
cast.file_reader
~~~~~~~~~~~~~~~~
Responsible for reading a source file from disk and returning its raw
content together with a list of individual lines (preserving all
whitespace and line endings stripped for convenience).
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple


class SourceFile(NamedTuple):
    path: Path
    content: str          # full raw text
    lines: list[str]      # content.splitlines() — 0-indexed internally


class FileReadError(Exception):
    """Raised when the file cannot be read."""


def read_source_file(path: str | Path) -> SourceFile:
    """
    Read *path* and return a :class:`SourceFile`.

    Raises
    ------
    FileReadError
        If the file does not exist, is not a regular file, or cannot be
        decoded as UTF-8.
    """
    p = Path(path).resolve()

    if not p.exists():
        raise FileReadError(f"File not found: {p}")
    if not p.is_file():
        raise FileReadError(f"Path is not a regular file: {p}")

    try:
        content = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Fall back to latin-1 — never raises on arbitrary bytes
        content = p.read_text(encoding="latin-1")
    except OSError as exc:
        raise FileReadError(f"Cannot read file {p}: {exc}") from exc

    return SourceFile(path=p, content=content, lines=content.splitlines())
