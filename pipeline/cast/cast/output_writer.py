"""
cast.output_writer
~~~~~~~~~~~~~~~~~~
Serialises the extracted chunks to a JSON file.

The output format is:
{
    "file_name": "example.js",
    "language":  "javascript",
    "total_chunks": 4,
    "chunks": [ { ...CodeChunk fields... }, ... ]
}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from cast.chunk_model import CodeChunk


def write_chunks(
    chunks: Sequence[CodeChunk],
    language: str,
    source_path: str | Path,
    output_path: str | Path = "chunks_output.json",
    *,
    indent: int = 2,
) -> Path:
    """
    Write *chunks* to *output_path* as JSON.

    Returns the resolved output :class:`~pathlib.Path`.
    """
    out = Path(output_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "file_name":    str(Path(source_path).resolve()),
        "language":     language,
        "total_chunks": len(chunks),
        "chunks":       [c.to_dict() for c in chunks],
    }

    out.write_text(json.dumps(payload, indent=indent, ensure_ascii=False), encoding="utf-8")
    return out
