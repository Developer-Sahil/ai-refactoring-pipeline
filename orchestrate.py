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
    parser.add_argument("input_file", help="Path to the source file in the 'input' folder")
    parser.add_argument("--model", default="gemini-2.5-flash", help="LLM model to use (default: gemini-2.5-flash)")
    parser.add_argument("--in-place", action="store_true", help="Overwrite the original source file")
    
    args = parser.parse_args()
    
    input_path = Path(args.input_file).resolve()
    if not input_path.exists():
        # Try finding it in the input folder if not provided as absolute path
        input_path = (Path("input") / args.input_file).resolve()
        if not input_path.exists():
            print(f"Error: Input file {args.input_file} not found.")
            sys.exit(1)

    root_dir = Path(__file__).parent.resolve()
    pipeline_dir = root_dir / "pipeline"
    output_dir = root_dir / "output"
    output_dir.mkdir(exist_ok=True)
    
    chunks_file = output_dir / "chunks_output.json"
    prompts_file = output_dir / "prompts.json"
    
    # Stage 1: cAST
    cast_env = os.environ.copy()
    cast_env["PYTHONPATH"] = str(pipeline_dir / "cast")
    cast_cmd = f'python -m cast.pipeline "{input_path}" "{chunks_file}" -v'
    run_command(cast_cmd, env=cast_env, description="Stage 1: cAST (Chunking)")
    
    # Stage 2: Prompt Builder
    pb_env = os.environ.copy()
    pb_env["PYTHONPATH"] = str(pipeline_dir / "prompt_builder")
    pb_cmd = f'python -m prompt_builder.build_prompts -i "{chunks_file}" -o "{prompts_file}" -v'
    run_command(pb_cmd, env=pb_env, description="Stage 2: Prompt Builder")
    
    # Stage 3: LLM Agent
    la_env = os.environ.copy()
    la_env["PYTHONPATH"] = str(pipeline_dir / "llm_agent")
    la_cmd = f'python -m llm_agent.run_agent --input "{prompts_file}" --model {args.model} --output-dir "{output_dir}"'
    if args.in_place:
        la_cmd += " --in-place"
    
    # We need to make sure llm_agent can find the source file. 
    # Current llm_agent logic is a bit rigid, it reads the filename from prompts.json
    # and expects it to be either absolute or relative to CWD.
    run_command(la_cmd, env=la_env, description="Stage 3: LLM Refactoring Agent")

    print("Pipeline execution finished successfully!")

if __name__ == "__main__":
    main()
