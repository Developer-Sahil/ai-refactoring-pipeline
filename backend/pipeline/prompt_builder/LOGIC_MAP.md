# Prompt Builder - Process Logic Map

This document maps the end-to-end execution flow of the Prompt Builder pipeline, detailing the exact order in which functions are called, and from which files.

---

## High-Level Execution Flow

The entire process is orchestrated through the entry point in `prompt_builder/build_prompts.py`.

### 1. Initialization and Orchestration (`prompt_builder/build_prompts.py`)
- **Function**: `main(argv)`
  - Parses command-line arguments (input, output, few-shot path, verbose) via `_build_arg_parser()`.
  - Calls `run()`, passing the file paths and logging parameters.
- **Function**: `run(input_path, output_path, few_shot_path, verbose)`
  - Acts as the central orchestrator, executing steps 2 through 6 in sequence.

### 2. Loading the cAST Output (`prompt_builder/build_prompts.py`)
- **Function**: `_load_chunks(path)`
  - Reads the `chunks_output.json` file produced by the cAST stage.
  - Validates basic schema (requires `file_name`, `language`, and a list of `chunks`).
  - Returns the JSON data as a dictionary.

### 3. Loading Few-Shot Examples (`prompt_builder/few_shot_loader.py`)
- **Class**: `FewShotLoader(path)`
  - Reads the `few_shot_examples.json` file.
  - **Method**: `__init__(path)`
    - Iterates over the examples list.
    - Indexes them by `(language, chunk_type)` in an internal dictionary.
    - Handles wildcards: exact matches win over type-wildcards, which win over language-wildcards.

### 4. Building Prompt Contexts (`prompt_builder/build_prompts.py`)
For every chunk in the input data:
- **Function**: `_chunk_to_context(chunk, language, full_file_content)`
  - Converts a raw dictionary chunk into a typed `PromptContext` object.
  - Injects the **full source file content** into every chunk context to provide the LLM with global architectural awareness.
  - Maps attributes like `chunk_id`, `chunk_type`, `name`, `code`, and line ranges.

### 5. Resolving and Rendering Prompts (`prompt_builder/prompt_templates.py`)
- **Function**: `render_prompt(ctx, file_name)`
  - **Class**: `TemplateRegistry`
    - **Method**: `resolve(language, chunk_type)`
      - Searches for the best-matching builder function based on a fallback chain:
        1. Exact Match: `(lang, ctype)`
        2. Language Wildcard: `(lang, "*")`
        3. Type Wildcard: `("*", ctype)`
        4. Global Default: `("*", "*")`
      - Returns the selected builder function (e.g., `build_class_prompt` or `build_standard_prompt`).
  - The builder function (e.g., `build_standard_prompt(ctx)`) renders the markdown prompt using `textwrap.dedent` and f-strings.
  - **Batching**: If `batch_size > 1`, `build_batch_prompt` is used to group multiple chunks into a single XML-tagged prompt, reducing API latency and cost.
  - Replaces the `{file_name}` placeholder in the template with the actual source filename.

### 6. Injecting Few-Shot Examples (`prompt_builder/build_prompts.py`)
- **Function**: `_append_few_shot(prompt, example, language)`
  - If a relevant example is found by the `FewShotLoader`, it is formatted into a "BEFORE/AFTER" block.
  - The block is appended to the bottom of the rendered base prompt.

### 7. Serialising Output to JSON (`prompt_builder/build_prompts.py`)
- **Function**: `_write_prompts(payload, path)`
  - Gathers all generated prompt records into a final output payload.
  - Writes the results to `output/prompts.json`.
  - Includes metadata like `file_name`, `total_prompts`, and `generated_at` timestamp.
