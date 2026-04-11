"""
llm_agent.code_replacer
~~~~~~~~~~~~~~~~~~~~~~~
Applies refactored code chunks back into their source files.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def replace_chunk(
    source_path: Path,
    start_line: int,
    end_line: int,
    new_code: str,
    output_path: Path | None = None
) -> Path:
    """
    Replace lines [start_line, end_line] (1-indexed, inclusive) in `source_path`
    with `new_code`.
    
    If `output_path` is provided, writes the result there instead of in-place.
    """
    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    # Read original lines (preserve newlines)
    with source_path.open("r", encoding="utf-8") as fh:
        lines = fh.readlines()

    if start_line < 1 or end_line > len(lines) or start_line > end_line:
        raise ValueError(
            f"Invalid line range [{start_line}, {end_line}] for file with {len(lines)} lines."
        )

    # Convert to 0-indexed for slice operations
    start_idx = start_line - 1
    end_idx = end_line

    # Detect original indentation of the first line
    original_first_line = lines[start_idx]
    indentation = ""
    for char in original_first_line:
        if char.isspace():
            indentation += char
        else:
            break
            
    # Prepare the new code lines
    new_raw_lines = new_code.splitlines()
    new_code_lines = []
    
    for line in new_raw_lines:
        # If the new line doesn't start with space but original was indented, 
        # apply the original indentation.
        if indentation and line and not line[0].isspace():
            new_code_lines.append(indentation + line + "\n")
        else:
            new_code_lines.append(line + "\n")
    
    # Replace the slice
    lines[start_idx:end_idx] = new_code_lines

    # Determine destination
    dest_path = output_path if output_path else source_path
    
    with dest_path.open("w", encoding="utf-8") as fh:
        fh.writelines(lines)

    logger.info("Successfully replaced lines %d–%d in %s", start_line, end_line, dest_path.name)
    return dest_path
