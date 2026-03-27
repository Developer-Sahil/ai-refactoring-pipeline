"""
cast.chunk_model
~~~~~~~~~~~~~~~~
Defines the CodeChunk dataclass — the canonical unit of output
for the cAST chunking pipeline stage.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class CodeChunk:
    """A self-contained logical unit extracted from a source file."""

    chunk_id: str                    # e.g. "chunk_1"
    type: str                        # "class" | "function" | "method" | "module" | ...
    name: Optional[str]              # identifier name, None for anonymous constructs
    start_line: int                  # 1-based inclusive
    end_line: int                    # 1-based inclusive
    code: str                        # verbatim source slice (original indentation preserved)
    metadata: dict = field(default_factory=dict)  # language-specific extras (parent class, etc.)

    # ------------------------------------------------------------------ #
    # Serialisation                                                        #
    # ------------------------------------------------------------------ #

    def to_dict(self) -> dict:
        d = {
            "chunk_id":   self.chunk_id,
            "type":       self.type,
            "name":       self.name,
            "start_line": self.start_line,
            "end_line":   self.end_line,
            "code":       self.code,
        }
        if self.metadata:
            d["metadata"] = self.metadata
        return d
