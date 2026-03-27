"""
cast.pipeline
~~~~~~~~~~~~~
Orchestrates the full cAST chunking stage:

  File → Read → Detect Language → Select Parser → Extract Chunks → Write JSON

Public API:  :func:`run`
CLI entry:   ``python -m cast <input_file> [output_file]``
"""

from __future__ import annotations

import sys
import argparse
import logging
from pathlib import Path

from cast.file_reader       import read_source_file, FileReadError
from cast.language_detector import detect_language, UnsupportedLanguageError
from cast.parsers.registry  import get_parser, list_supported_languages
from cast.output_writer     import write_chunks

logger = logging.getLogger(__name__)


def run(
    input_file: str | Path,
    output_file: str | Path = "chunks_output.json",
    *,
    verbose: bool = False,
) -> Path:
    """
    Execute the full cAST chunking pipeline for a single source file.

    Parameters
    ----------
    input_file:
        Path to the source file to analyse.
    output_file:
        Destination path for the generated JSON (default: ``chunks_output.json``
        in the current working directory).
    verbose:
        If *True* emit progress messages to stdout.

    Returns
    -------
    pathlib.Path
        Resolved path to the written JSON file.

    Raises
    ------
    FileReadError
        If the source file cannot be read.
    UnsupportedLanguageError
        If the file extension maps to no known language.
    KeyError
        If the language has no registered parser.
    """
    def log(msg: str) -> None:
        if verbose:
            print(f"[cAST] {msg}")

    # ── 1. Read source file ───────────────────────────────────────────────
    log(f"Reading  : {input_file}")
    source = read_source_file(input_file)
    log(f"Lines    : {len(source.lines)}")

    # ── 2. Detect language ────────────────────────────────────────────────
    language = detect_language(source.path)
    log(f"Language : {language}")

    # ── 3. Select parser ─────────────────────────────────────────────────
    parser = get_parser(language)
    log(f"Parser   : {parser.__class__.__name__}")

    # ── 4. Extract chunks ─────────────────────────────────────────────────
    log("Extracting chunks …")
    chunks = parser.extract_chunks(source)
    log(f"Found    : {len(chunks)} chunk(s)")

    # ── 5. Write output ───────────────────────────────────────────────────
    log(f"Writing  : {output_file}")
    out_path = write_chunks(
        chunks,
        language=language,
        source_path=source.path,
        output_path=output_file,
    )
    log(f"Done     : {out_path}")
    return out_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cast",
        description="cAST — Code AST-based Chunking.  Stage 1 of the AI refactoring pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Supported languages:\n  "
            + "\n  ".join(list_supported_languages())
        ),
    )
    p.add_argument(
        "input_file",
        metavar="INPUT",
        help="Path to the source file to analyse.",
    )
    p.add_argument(
        "output_file",
        metavar="OUTPUT",
        nargs="?",
        default="chunks_output.json",
        help="Destination JSON file (default: chunks_output.json).",
    )
    p.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print progress information.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    try:
        out = run(args.input_file, args.output_file, verbose=args.verbose)
        print(f"Output written to: {out}")
        return 0
    except (FileReadError, UnsupportedLanguageError, KeyError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
