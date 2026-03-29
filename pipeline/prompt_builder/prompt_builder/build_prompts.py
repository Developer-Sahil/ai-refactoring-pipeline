"""
prompt_builder.build_prompts
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Stage 2 of the AI refactoring pipeline — Prompt Builder.

Reads ``chunks_output.json`` produced by the cAST stage, generates a
structured LLM refactoring prompt for every chunk, and writes the result
to ``outputs/prompts.json``.

Usage (library)
---------------
>>> from prompt_builder.build_prompts import run
>>> run("cast/chunks_output.json", "outputs/prompts.json", verbose=True)

Usage (CLI)
-----------
    python -m prompt_builder.build_prompts  \\
           --input  cast/chunks_output.json \\
           --output outputs/prompts.json    \\
           --verbose
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from prompt_builder.prompt_templates import PromptContext, render_prompt, build_batch_prompt
from prompt_builder.few_shot_loader  import FewShotLoader


# ── I/O helpers ───────────────────────────────────────────────────────────────

def _load_chunks(path: Path) -> dict[str, Any]:
    """Load and validate the cAST output file."""
    if not path.exists():
        raise FileNotFoundError(f"cAST output not found: {path}")
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)

    # Basic schema validation
    for required in ("file_name", "language", "chunks"):
        if required not in data:
            raise ValueError(f"chunks_output.json is missing required key: '{required}'")
    if not isinstance(data["chunks"], list):
        raise ValueError("'chunks' must be a JSON array")

    return data


def _write_prompts(payload: dict, path: Path) -> None:
    """Serialise *payload* to *path*, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)


# ── Chunk → PromptContext ──────────────────────────────────────────────────────

def _chunk_to_context(chunk: dict[str, Any], language: str, full_file_content: Optional[str] = None) -> PromptContext:
    """Convert a raw cAST chunk dict to a typed :class:`PromptContext`."""
    return PromptContext(
        chunk_id   = chunk["chunk_id"],
        chunk_type = chunk.get("type", "unknown"),
        name       = chunk.get("name"),
        language   = language,
        code       = chunk.get("code", ""),
        start_line = chunk.get("start_line", 0),
        end_line   = chunk.get("end_line", 0),
        full_file_content = full_file_content,
        metadata   = chunk.get("metadata", {}),
    )


# ── Prompt record ─────────────────────────────────────────────────────────────

def _build_batch_prompt_record(
    chunks: list[dict[str, Any]],
    language: str,
    file_name: str,
    few_shot_loader: FewShotLoader,
    full_file_content: Optional[str] = None,
) -> dict[str, Any]:
    """Return a single prompt record covering multiple chunks."""
    contexts = [_chunk_to_context(c, language, full_file_content) for c in chunks]
    
    # Use the first chunk's type to fetch a relevant few-shot example
    example = few_shot_loader.get(language, contexts[0].chunk_type)
    prompt = build_batch_prompt(contexts, file_name, few_shot_example=example)
    
    return {
        "is_batch": True,
        "chunk_ids": [c["chunk_id"] for c in chunks],
        "chunks": chunks, # Keep original chunk data for the agent
        "prompt": prompt,
    }

def _build_prompt_record(
    chunk: dict[str, Any],
    language: str,
    file_name: str,
    few_shot_loader: FewShotLoader,
    full_file_content: Optional[str] = None,
) -> dict[str, Any]:
    """Return the full prompt record for a single chunk."""
    ctx    = _chunk_to_context(chunk, language, full_file_content)
    prompt = render_prompt(ctx, file_name)

    # Optionally append a few-shot example if one exists for this (language, type)
    example = few_shot_loader.get(language, ctx.chunk_type)
    if example:
        prompt = _append_few_shot(prompt, example, language)

    return {
        "is_batch":     False,
        "chunk_id":      ctx.chunk_id,
        "chunk_type":    ctx.chunk_type,
        "name":          ctx.name,
        "start_line":    ctx.start_line,
        "end_line":      ctx.end_line,
        "original_code": ctx.code,
        "prompt":        prompt,
    }


def _append_few_shot(prompt: str, example: dict, language: str) -> str:
    """Append a before/after few-shot demonstration to the prompt."""
    separator = "\n\n── Few-Shot Example ─────────────────────────────────────────────────────"
    block = (
        f"{separator}\n"
        f"The following is an example of the quality and style of refactoring expected.\n\n"
        f"BEFORE:\n```{language}\n{example['before']}\n```\n\n"
        f"AFTER:\n```{language}\n{example['after']}\n```\n"
        f"Note: {example.get('notes', '')}"
    )
    return prompt + block


# ── Pipeline entry-point ──────────────────────────────────────────────────────

def run(
    input_path:  str | Path = "cast/chunks_output.json",
    output_path: str | Path = "outputs/prompts.json",
    few_shot_path: Optional[str | Path] = None,
    *,
    verbose: bool = False,
    batch_size: int = 1,
) -> Path:
    """
    Execute the full Prompt Builder stage.

    Parameters
    ----------
    input_path:
        Path to the ``chunks_output.json`` file produced by cAST.
    output_path:
        Destination for the generated ``prompts.json``.
    few_shot_path:
        Optional override for the few-shot examples JSON file.
        Defaults to ``few_shot_examples.json`` beside this module.
    verbose:
        Print progress messages to stdout.

    Returns
    -------
    pathlib.Path
        Resolved path of the written ``prompts.json``.
    """
    inp = Path(input_path).resolve()
    out = Path(output_path).resolve()

    def log(msg: str) -> None:
        if verbose:
            print(f"[PromptBuilder] {msg}")

    # ── 1. Load cAST output ──────────────────────────────────────────────────
    log(f"Loading   : {inp}")
    data      = _load_chunks(inp)
    file_name = data["file_name"]
    language  = data["language"]
    chunks    = data["chunks"]
    
    # Attempt to load the full source file for context
    full_file_content = None
    source_path = Path(file_name)
    if source_path.exists():
        try:
            full_file_content = source_path.read_text(encoding="utf-8")
            log(f"Context   : Loaded {len(full_file_content)} chars from {source_path.name}")
        except Exception as e:
            log(f"Warning   : Could not read source file for context: {e}")
    else:
        log(f"Warning   : Source file not found for context: {file_name}")

    log(f"File      : {file_name}  |  Language : {language}  |  Chunks : {len(chunks)}")

    # ── 2. Load few-shot examples ────────────────────────────────────────────
    fs_path = Path(few_shot_path) if few_shot_path else (
        Path(__file__).parent / "few_shot_examples.json"
    )
    few_shot_loader = FewShotLoader(fs_path)
    log(f"Few-shots : {few_shot_loader.count} examples loaded from {fs_path.name}")

    # ── 3. Build prompt records (batched or single) ──────────────────────────
    log(f"Building prompts (batch_size={batch_size}) …")
    prompt_records: list[dict] = []
    
    if batch_size > 1:
        # Group chunks into batches
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            record = _build_batch_prompt_record(batch, language, file_name, few_shot_loader, full_file_content)
            prompt_records.append(record)
            log(f"  ✓ Batch {len(prompt_records)}: [{', '.join(record['chunk_ids'])}]")
    else:
        # One prompt per chunk
        for chunk in chunks:
            record = _build_prompt_record(chunk, language, file_name, few_shot_loader, full_file_content)
            prompt_records.append(record)
            log(f"  ✓ {record['chunk_id']:10s}  [{record['chunk_type']:15s}]  {record['name'] or '(anonymous)'}")

    # ── 4. Assemble output payload ───────────────────────────────────────────
    payload = {
        "file_name":     file_name,
        "language":      language,
        "total_prompts": len(prompt_records),
        "generated_at":  datetime.now(timezone.utc).isoformat(),
        "prompts":       prompt_records,
    }

    # ── 5. Write output ──────────────────────────────────────────────────────
    log(f"Writing   : {out}")
    _write_prompts(payload, out)
    log(f"Done      : {len(prompt_records)} prompt(s) written to {out}")

    return out


# ── CLI ────────────────────────────────────────────────────────────────────────

def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="prompt_builder",
        description=(
            "Stage 2 of the AI refactoring pipeline.\n"
            "Reads cAST chunk output and generates structured LLM prompts."
        ),
    )
    p.add_argument(
        "-i", "--input",
        default="cast/chunks_output.json",
        metavar="PATH",
        help="Path to chunks_output.json (default: cast/chunks_output.json)",
    )
    p.add_argument(
        "-o", "--output",
        default="outputs/prompts.json",
        metavar="PATH",
        help="Destination prompts.json (default: outputs/prompts.json)",
    )
    p.add_argument(
        "--few-shot",
        default=None,
        metavar="PATH",
        help="Path to few_shot_examples.json (optional override)",
    )
    p.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print progress information",
    )
    p.add_argument(
        "--batch-size",
        type=int,
        default=1,
        help="Number of chunks to group into a single prompt (default: 1)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    try:
        out = run(
            input_path    = args.input,
            output_path   = args.output,
            few_shot_path = args.few_shot,
            verbose       = args.verbose,
            batch_size    = args.batch_size,
        )
        print(f"Prompts written to: {out}")
        return 0
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
