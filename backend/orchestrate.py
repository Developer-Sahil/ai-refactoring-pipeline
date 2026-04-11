import os
import subprocess
import sys
import argparse
from pathlib import Path

def run_command(command, env=None, description=""):
    print(f"--- Running {description} ---")
    print(f"Command: {command}")
    result = subprocess.run(command, env=env, shell=True)
    if result.returncode != 0:
        print(f"Error: {description} failed with return code {result.returncode}")
        sys.exit(result.returncode)
    print(f"--- {description} completed successfully ---\n")

def main():
    parser = argparse.ArgumentParser(description="Standard Development Pipeline Orchestrator")
    parser.add_argument("inputs", nargs="+", help="Paths to source files or folders in the 'input' folder")
    parser.add_argument(
        "--model",
        default="gemini-2.5-flash",
        help="Model to use (default: gemini-2.5-flash)",
    )
    parser.add_argument("--in-place", action="store_true", help="Overwrite the original source file")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between LLM requests in seconds (default: 2.0)")
    parser.add_argument("--batch-size", type=int, default=3, help="Number of chunks to process in one LLM call (default: 3)")
    
    args = parser.parse_args()
    
    # 1. Collect all input files
    source_files = []
    for input_item in args.inputs:
        input_path = Path(input_item).resolve()
        if not input_path.exists():
            # Try finding it in the backend/input folder relative to this script
            input_path = (Path(__file__).parent / "input" / input_item).resolve()
            
        if not input_path.exists():
            print(f"Warning: Input {input_item} not found. Skipping.")
            continue
            
        if input_path.is_dir():
            # Add all .py files in the directory
            source_files.extend(list(input_path.glob("*.py")))
        else:
            source_files.append(input_path)

    if not source_files:
        print("Error: No valid source files found to process.")
        sys.exit(1)

    root_dir = Path(__file__).parent.resolve()
    pipeline_dir = root_dir / "pipeline"
    output_dir = root_dir / "output"
    output_dir.mkdir(exist_ok=True)
    
    # 2. Process each file in the pipeline
    total = len(source_files)
    for idx, input_path in enumerate(source_files, start=1):
        filename = input_path.name
        print(f"================================================================")
        print(f" Processing File {idx}/{total}: {filename}")
        print(f"================================================================")
        
        # Unique artifacts for this specific run
        chunks_file = output_dir / f"{input_path.stem}_chunks.json"
        prompts_file = output_dir / f"{input_path.stem}_prompts.json"
        
        # Stage 1: cAST
        cast_env = os.environ.copy()
        cast_env["PYTHONPATH"] = str(pipeline_dir / "cast")
        cast_cmd = f'python -m cast.pipeline "{input_path}" "{chunks_file}" -v'
        run_command(cast_cmd, env=cast_env, description=f"Stage 1: cAST (Chunking) - {filename}")
        
        # Stage 2: Prompt Builder
        pb_env = os.environ.copy()
        pb_env["PYTHONPATH"] = str(pipeline_dir / "prompt_builder")
        pb_cmd = f'python -m prompt_builder.build_prompts -i "{chunks_file}" -o "{prompts_file}" --batch-size {args.batch_size} -v'
        run_command(pb_cmd, env=pb_env, description=f"Stage 2: Prompt Builder - {filename}")
        
        # Stage 3: LLM Agent
        la_env = os.environ.copy()
        la_env["PYTHONPATH"] = str(pipeline_dir / "llm_agent")
        la_cmd = f'python -m llm_agent.run_agent --input "{prompts_file}" --model {args.model} --output-dir "{output_dir}" --delay {args.delay}'
        if args.in_place:
            la_cmd += " --in-place"
        
        run_command(la_cmd, env=la_env, description=f"Stage 3: LLM Refactoring Agent - {filename}")

        # After Stage 3 completes:
        result = run_validation(
            original_file=Path(args.input_file),
            refactored_file=Path(f"{output_dir}/{filename}.refactored{ext}"),
            test_dir=Path("tests"),  # if exists
        )

        if not result.passed:
            print("❌ Validation failed! Refactored code not suitable for release.")
            print(result.report)
            sys.exit(1)

        print("✅ All validation checks passed. Code ready for delivery.")
        shutil.copy(refactored_file, final_output_dir)

    print(f"Pipeline execution finished successfully for {total} file(s)!")

if __name__ == "__main__":
    main()
