"""
llm_agent.run_agent
~~~~~~~~~~~~~~~~~~~
Orchestrates Stage 3: reading prompts, calling the LLM, parsing, and replacing code.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from llm_agent.llm_client import LLMClient
from llm_agent.response_parser import parse_code_block, parse_batched_blocks
from llm_agent.code_replacer import replace_chunk

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("llm_agent")


def run(
    prompts_file: str | Path,
    model: str = "gemini-2.5-flash",
    in_place: bool = False,
    dry_run: bool = False,
    output_dir: str | Path | None = None,
    delay: float = 0,
) -> None:
    """Execute the Stage 3 agent pipeline."""
    prompts_path = Path(prompts_file).resolve()
    
    if not prompts_path.exists():
        logger.error("Prompts file not found: %s", prompts_path)
        sys.exit(1)
        
    with prompts_path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    
    # Try to find the source file. Stage 1/2 might just record 'order_service.py'.
    # We'll look for it in the current directory or cast/cast/tests/
    source_file_raw = data["file_name"]
    source_file = Path(source_file_raw)
    
    if not source_file.exists():
        # Fallback check for our test file
        test_fallback = Path("cast/cast/tests") / source_file.name
        if test_fallback.exists():
            source_file = test_fallback
            logger.info("Auto-resolved source file to: %s", source_file)
            
    if not source_file.exists():
        logger.error("Source file referenced in prompts not found: %s", source_file_raw)
        sys.exit(1)
        
    prompts = data.get("prompts", [])
    logger.info("Processing %d prompts for file: %s", len(prompts), source_file.name)
    
    if not dry_run:
        try:
            client = LLMClient(model=model)
            logger.info("Initialized LLM Client (model=%s)", model)
        except ValueError as e:
            logger.error("Initialization error: %s", e)
            sys.exit(1)
            
    # Determine destination folder (llm_agent/output/ or user-defined)
    if not dry_run:
        output_dir = Path(output_dir).resolve() if output_dir else Path(__file__).parent.parent / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
    
    # If not in place, we write to the output folder
    dest_file = source_file
    if not in_place and not dry_run:
        dest_filename = f"{source_file.stem}.refactored{source_file.suffix}"
        dest_file = output_dir / dest_filename
        
        # Copy the original file to the dest_file to start applying chunks to it
        dest_file.write_text(source_file.read_text(encoding="utf-8"), encoding="utf-8")
        logger.info("Writing refactored output to safe copy: %s", dest_file)

    success_count = 0
    
    # Process chunks in REVERSE order. 
    # If we process top-down and a chunk changes the line count, 
    # all subsequent start_line/end_line coordinates become invalid.
    # Process prompts in REVERSE order. 
    # For batches, we sort by the START line of the FIRST chunk in the batch.
    # Filter out nested prompts to avoid redundant refactorings and file corruption.
    # If Chunk A is inside Chunk B, and we refactor Chunk B, the LLM will already
    # refactor the code of Chunk A as part of the process.
    def get_start_line(p):
        if p.get("is_batch"):
            return min(c["start_line"] for c in p["chunks"])
        return p["start_line"]
        
    def get_effective_chunks(p):
        if p.get("is_batch"):
            return p["chunks"]
        return [p]

    final_prompts = []
    # Sort prompts so we check larger ones first or at least consistently
    all_prompts = sorted(prompts, key=get_start_line) # Top-down
    
    for i, p in enumerate(all_prompts):
        is_nested = False
        p_chunks = get_effective_chunks(p)
        
        for p_chunk in p_chunks:
            p_start, p_end = p_chunk["start_line"], p_chunk["end_line"]
            
            # Check against ALL OTHER chunks in ALL OTHER prompts
            for j, pf in enumerate(all_prompts):
                if i == j: continue
                pf_chunks = get_effective_chunks(pf)
                for pf_chunk in pf_chunks:
                    pf_start, pf_end = pf_chunk["start_line"], pf_chunk["end_line"]
                    
                    # If p_chunk is inside pf_chunk
                    if pf_start <= p_start and pf_end >= p_end:
                        # If boundaries are same, pick the one that appeared first in list or has more lines
                        if pf_start == p_start and pf_end == p_end:
                            if j < i: # Other one came first
                                is_nested = True
                                break
                        else:
                            # pf is strictly larger
                            is_nested = True
                            break
                if is_nested: break
            if is_nested: break
            
        if is_nested:
            logger.info("Skipping nested/redundant prompt: %s", p.get("chunk_ids") or p.get("chunk_id"))
            continue
        final_prompts.append(p)

    sorted_prompts = sorted(final_prompts, key=get_start_line, reverse=True)
    
    for prompt_data in sorted_prompts:
        is_batch = prompt_data.get("is_batch", False)
        
        if is_batch:
            chunk_id = f"Batch[{', '.join(prompt_data['chunk_ids'])}]"
            name = "multiple"
            # Get the overall range for logging
            start_line = min(c["start_line"] for c in prompt_data["chunks"])
            end_line = max(c["end_line"] for c in prompt_data["chunks"])
        else:
            chunk_id = prompt_data["chunk_id"]
            name = prompt_data.get("name", "unknown")
            start_line = prompt_data["start_line"]
            end_line = prompt_data["end_line"]
        
        prompt_text = prompt_data["prompt"]
        
        logger.info("Processing %s (%s) lines %d-%d", chunk_id, name, start_line, end_line)
        
        if dry_run:
            logger.info("[DRY RUN] Would send prompt (length: %d chars)", len(prompt_text))
            continue
            
        try:
            logger.debug("Generating response from LLM...")
            raw_response = client.generate_response(prompt_text)
            
            if prompt_data.get("is_batch"):
                # ── BATCHED REPLACEMENT ──
                extracted_blocks = parse_batched_blocks(raw_response)
                
                # Chunks in the batch must also be applied in REVERSE order
                batch_chunks = sorted(prompt_data["chunks"], key=lambda c: c["start_line"], reverse=True)
                
                for chunk in batch_chunks:
                    c_id = chunk["chunk_id"]
                    if c_id not in extracted_blocks:
                        logger.warning("Chunk %s was missing from batched response.", c_id)
                        continue
                        
                    replace_chunk(
                        source_path=dest_file if not in_place else source_file,
                        start_line=chunk["start_line"],
                        end_line=chunk["end_line"],
                        new_code=extracted_blocks[c_id],
                        output_path=dest_file
                    )
                    success_count += 1
            else:
                # ── INDIVIDUAL REPLACEMENT ──
                refactored_code = parse_code_block(raw_response)
                
                if not refactored_code:
                    logger.warning("No code extracted for %s. Skipping.", chunk_id)
                    continue
                    
                replace_chunk(
                    source_path=dest_file if not in_place else source_file,
                    start_line=start_line,
                    end_line=end_line,
                    new_code=refactored_code,
                    output_path=dest_file
                )
                success_count += 1
            
            # Rate limit mitigation: wait between requests
            if delay > 0 and prompt_data != sorted_prompts[-1]:
                logger.info("Waiting %.1fs before next batch...", delay)
                time.sleep(delay)
                
        except Exception as e:
            logger.error("Failed to process %s: %s", chunk_id, e)
            
    if dry_run:
        logger.info("[DRY RUN] Completed. No files modified.")
    else:
        if success_count == 0 and len(prompts) > 0:
            logger.error("No chunks were successfully refactored. Check API keys/limits.")
            sys.exit(1)
        logger.info("Completed %d/%d refactorings successfully. Output: %s", success_count, len(prompts), dest_file)


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 3: LLM Refactoring Agent")
    parser.add_argument(
        "-i", "--input",
        required=True,
        help="Path to prompts.json (generated by Stage 2)"
    )
    parser.add_argument(
        "--model",
        default="gemini-2.5-flash",
        help="Model to use (default: gemini-2.5-flash)"
    )
    parser.add_argument(
        "--output-dir",
        help="Folder to save refactored files (default: pipeline/llm_agent/output/)"
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite the original source file instead of creating a .refactored copy"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Seconds to wait between LLM requests to avoid rate limits (default: 4.0)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse the prompt file but do not call the LLM or write files"
    )
    
    args = parser.parse_args()
    run(
        prompts_file=args.input,
        model=args.model,
        in_place=args.in_place,
        dry_run=args.dry_run,
        output_dir=args.output_dir,
        delay=args.delay
    )


if __name__ == "__main__":
    main()
