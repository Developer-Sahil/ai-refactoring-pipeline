# LLM Refactoring Agent - Process Logic Map

This document maps the end-to-end execution flow of the LLM Refactoring Agent pipeline, detailing the exact order in which functions are called.

---

## High-Level Execution Flow

The entire process is orchestrated through the entry point in `llm_agent/run_agent.py`.

### 1. Initialization and Orchestration (`run_agent.py`)
- **Function**: `main()`
  - Parses command-line arguments using `argparse`.
  - Arguments include the input path (`--input`), the model name (`--model`), the execution mode (`--in-place`), and a debugging flag (`--dry-run`).
  - Calls `run()`, passing the parsed parameters.
  
- **Function**: `run(...)`
  - Loads the Stage 2 output JSON file.
  - Validates the existence of the original source file referenced within the JSON payload.
  - Instantiates the `LLMClient`.
  - Creates a copy of the source file (e.g., `filename.refactored.ext`) if not running in-place.
  - **Crucial Step**: Sorts the prompt chunks by `start_line` in **descending order** (bottom-to-top). This prevents a replacement from shifting the line numbers of subsequent target chunks.

### 2. Calling the LLM (`llm_client.py`)
For each chunk in the sorted list:
- **Class**: `LLMClient`
  - **Method**: `generate_response(prompt)`
    - Constructs the request using the `google.genai` SDK.
    - Captures the response text.
    - Automatically catches transient errors (429, 503) and applies exponential backoff up to 3 times before failing.

### 3. Parsing the Output (`response_parser.py`)
- **Function**: `parse_code_block(response_text)`
  - Uses regular expressions to scan the LLMl response for markdown code blocks (````python ... ````).
  - Strips the markdown wrapper and language identifier.
  - Returns the raw refactored code string. Falls back to the raw response if no formatting blocks are found.

### 4. Replacing the Code (`code_replacer.py`)
- **Function**: `replace_chunk(source_path, start_line, end_line, new_code, output_path)`
  - Opens the target file (the `.refactored.ext` copy).
  - Reads all lines into memory.
  - Converts the 1-indexed `start_line` and `end_line` coordinates from Stage 1 into 0-indexed list slice coordinates.
  - Splits the `new_code` string and replaces the slice within the line array.
  - Overwrites the file with the updated array.
  - Execution returns to `run()` to process the next chunk up the file.

### 5. Completion
- Once all chunks are processed, execution terminates, leaving the user with a fully populated `refactored` source file containing all the AI modifications.
