# cAST - Process Logic Map

This document maps the end-to-end execution flow of the cAST (Code AST-based Chunking) extraction pipeline, detailing the exact order in which functions are called, and from which files.

---

## High-Level Execution Flow

The entire process is orchestrated through the entry point in `cast/pipeline.py`.

### 1. Initialization and Orchestration (`cast/pipeline.py`)
- **Function**: `main(argv)`
  - Parses command-line arguments via `_build_arg_parser()`.
  - Calls `run()`, passing the `input_file` and `output_file` paths.
- **Function**: `run(input_file, output_file, verbose)`
  - Acts as the central orchestrator, executing steps 2 through 6 in sequence.

### 2. Reading the Source File (`cast/file_reader.py`)
- **Function**: `read_source_file(path)`
  - Called by `run()`.
  - Reads the file from disk (handles UTF-8 or Fallback latin-1).
  - Returns a `SourceFile` object containing the file path, raw content text, and a list of split lines.

### 3. Detecting the Programming Language (`cast/language_detector.py`)
- **Function**: `detect_language(path)`
  - Called by `run()`.
  - Inspects the file extension of the input file.
  - Maps the extension to a canonical language string (e.g., `".ts"` -> `"typescript"`) using the `EXTENSION_MAP`.

### 4. Selecting the Core Parser (`cast/parsers/registry.py`)
- **Function**: `get_parser(language)`
  - Called by `run()`.
  - Looks up the language string in the `_REGISTRY` dictionary.
  - Returns the appropriate parser instance which inherits from `BaseParser` (from `cast/parsers/base_parser.py`).
- **Function**: `_get_parser_with_fallback(language)` *(called at module load time to populate `_REGISTRY`)*
  - Attempts to instantiate `TreeSitterParser(language)`.
  - If tree-sitter bindings are unavailable (`ImportError` or `ValueError`), falls back to `BraceLanguageParser(language)`.

### 5. Extracting Code Chunks 
Called via `parser.extract_chunks(source)` from `run()`. The execution branches based on the parser selected:

#### Branch A: Python File (`cast/parsers/python_parser.py`)
- Extracted using the `PythonParser` class.
- **Method**: `extract_chunks(source)`
  - Parses the raw code text into an Abstract Syntax Tree (AST) using Python's standard `ast.parse()`.
  - Walks the AST using `ast.walk(tree)`.
  - **Method**: `_is_top_level(node, tree)` validates top-level functions vs. class methods.
  - **Method**: `_node_to_chunk(node, chunk_type, source, index, metadata)` converts an AST node to a structured `CodeChunk`.

#### Branch B: Tree-sitter Languages — JS, TS, Java, C, C++, Go, Rust, Ruby, PHP (`cast/parsers/tree_sitter_parser.py`)
- Extracted using the `TreeSitterParser` class (primary parser).
- **Method**: `__init__(language)` loads the grammar from the corresponding `tree_sitter_*` package and builds a reverse mapping of AST node types to chunk types.
- **Method**: `extract_chunks(source)`
  - Encodes the file into bytes and parses it via `self._parser.parse()`.
  - **Method**: `_walk_tree(node, source, chunks)` recursively walks the AST `root_node`, matching `node.type` against the language-specific target node types (e.g., `class_declaration`, `function_definition`, `method_declaration`).
  - **Method**: `_extract_identifier(node)` finds the name of the structural unit by inspecting child nodes for `identifier`, `name`, `type_identifier`, etc.
  - **Method**: `_is_js_arrow_function(node)` filters JS/TS `lexical_declaration` nodes to only extract actual arrow/function expressions.
  - **Method**: `_find_go_type_kind(node)` differentiates Go `struct` from `interface` within `type_declaration` nodes.

#### Branch C: Fallback — Brace-Delimited Languages (`cast/parsers/brace_language_parser.py`)
- Only used if tree-sitter bindings are unavailable for JS, TS, Java, C, C++, or Go.
- **Method**: `extract_chunks(source)`
  - Iterates over source lines sequentially.
  - **Method**: `_match_line(line)` uses pre-compiled language-specific regular expressions to detect the beginning of structural units.
  - **Method**: `_find_closing_brace(lines, start_idx)` scans forward handling comments and strings using a mini state machine, returning the end line of the matching closing brace (`}`).
  - **Method**: `_is_nested(...)` ensures inner structures don't duplicate broader scope extractions.

#### Shared Parser Helpers (`cast/parsers/base_parser.py`)
All parsers employ these helper methods from `BaseParser`:
- **Method**: `slice_lines(lines, start_line, end_line)` extracts the verbatim text block based on line indices.
- **Method**: `make_chunk_id(index)` formats the deterministic incrementing ID (e.g., `"chunk_1"`).

### 6. Serialising outputs to JSON (`cast/output_writer.py`)
- **Function**: `write_chunks(chunks, language, source_path, output_path)`
  - Called by `run()` after chunks are successfully extracted.
  - Accepts the list of `CodeChunk` objects and writes them dynamically to the output JSON file.
  - Serializes chunk objects payload with `c.to_dict()`.
  - Returns the resolved Path for the generated JSON file, returning control back to `main()` where execution terminates gracefully.
