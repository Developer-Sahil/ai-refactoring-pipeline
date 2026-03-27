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
from pathlib import Path

from llm_agent.llm_client import LLMClient
from llm_agent.response_parser import parse_code_block
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
) -> None:
    """Execute the Stage 3 agent pipeline."""
    prompts_path = Path(prompts_file).resolve()
    
    if not prompts_path.exists():
        logger.error("Prompts file not found: %s", prompts_path)
        sys.exit(1)
        
    logger.info("Loading prompts from %s", prompts_path.name)
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
    sorted_prompts = sorted(prompts, key=lambda p: p["start_line"], reverse=True)
    
    for prompt_data in sorted_prompts:
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
            
        except Exception as e:
            logger.error("Failed to process %s: %s", chunk_id, e)
            
    if dry_run:
        logger.info("[DRY RUN] Completed. No files modified.")
    else:
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
        help="Gemini model to use (default: gemini-2.5-flash)"
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
        output_dir=args.output_dir
    )


if __name__ == "__main__":
    main()
