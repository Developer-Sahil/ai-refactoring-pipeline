# cAST — Code AST-based Chunking

> **Stage 1 of the AI-powered code refactoring pipeline.**
> Parses a source file, extracts every logical structural unit (class,
> function, method, interface …) as a self-contained chunk, and writes
> the result to a JSON file for downstream analysis.

---

## Table of Contents

1. [Architecture](#architecture)
2. [Quick Start](#quick-start)
3. [Supported Languages](#supported-languages)
4. [Output Format](#output-format)
5. [Module Reference](#module-reference)
6. [How to Add a New Language Parser](#how-to-add-a-new-language-parser)
7. [Running the Tests](#running-the-tests)

---

## Architecture

```
cast/
├── __init__.py               ← Public API  (run)
├── pipeline.py               ← Orchestrator + CLI entry-point
│
├── file_reader.py            ← 1. Read source file from disk
├── language_detector.py      ← 2. Map file extension → language id
├── output_writer.py          ← 6. Serialise chunks → JSON
│
└── parsers/
    ├── base_parser.py            ← Abstract base class (contract)
    ├── python_parser.py          ← Python  – uses stdlib `ast` module
    ├── tree_sitter_parser.py     ← JS/TS/Java/C/C++/Go/Rust/Ruby/PHP – tree-sitter AST
    ├── brace_language_parser.py  ← Legacy fallback – regex + brace tracker
    └── registry.py               ← Language → parser factory (with graceful fallback)
```

### Data flow

```
  Input file
      │
      ▼
  FileReader          reads raw text, produces SourceFile(path, content, lines)
      │
      ▼
  LanguageDetector    maps ".py" → "python", ".ts" → "typescript", …
      │
      ▼
  ParserRegistry      returns the correct BaseParser subclass
      │
      ▼
  Parser.extract_chunks()   walks the AST / syntax tree → list[CodeChunk]
      │
      ▼
  OutputWriter        serialises to chunks_output.json
```

---

## Quick Start

### As a library

```python
from cast.pipeline import run

output_path = run(
    input_file="src/order_service.py",
    output_file="chunks_output.json",
    verbose=True,
)
print(f"Chunks written to {output_path}")
```

### As a CLI tool

```bash
# basic usage (output defaults to chunks_output.json)
python -m cast.pipeline  src/cart.js

# explicit output path + verbose progress
python -m cast.pipeline  src/user-service.ts  output/ts_chunks.json  --verbose
```

---

## Supported Languages

| Extension(s)           | Language   | Parser              |
|------------------------|------------|---------------------|
| `.py` `.pyw`           | Python     | `PythonParser` (stdlib `ast`) |
| `.js` `.mjs` `.cjs`    | JavaScript | `TreeSitterParser` |
| `.ts` `.tsx`           | TypeScript | `TreeSitterParser` |
| `.java`                | Java       | `TreeSitterParser` |
| `.c` `.h`              | C          | `TreeSitterParser` |
| `.cpp` `.cc` `.hpp` …  | C++        | `TreeSitterParser` |
| `.go`                  | Go         | `TreeSitterParser` |
| `.rs`                  | Rust       | `TreeSitterParser` |
| `.rb`                  | Ruby       | `TreeSitterParser` |
| `.php`                 | PHP        | `TreeSitterParser` |

---

## Output Format

```json
{
  "file_name": "cart.js",
  "language": "javascript",
  "total_chunks": 4,
  "chunks": [
    {
      "chunk_id": "chunk_1",
      "type": "class",
      "name": "CartItem",
      "start_line": 12,
      "end_line": 33,
      "code": "class CartItem {\n    constructor(productId, name, price, quantity = 1) {\n        ..."
    },
    {
      "chunk_id": "chunk_3",
      "type": "function",
      "name": "calculateDiscount",
      "start_line": 96,
      "end_line": 100,
      "code": "function calculateDiscount(code, subtotal) {\n    const discounts = ..."
    }
  ]
}
```

### Chunk fields

| Field        | Type            | Description                                     |
|--------------|-----------------|-------------------------------------------------|
| `chunk_id`   | `string`        | Unique identifier within the file (`chunk_1`, …)|
| `type`       | `string`        | `class` · `function` · `async_function` · `method` · `async_method` · `interface` · `struct` · `enum` · `constructor` · `namespace` · `type_alias` |
| `name`       | `string\|null`  | Declared identifier; `null` for anonymous constructs |
| `start_line` | `int`           | First line of the chunk (1-based, inclusive)    |
| `end_line`   | `int`           | Last line of the chunk (1-based, inclusive)     |
| `code`       | `string`        | Verbatim source slice — original formatting preserved |
| `metadata`   | `object`        | Optional extras (e.g. `parent_class` for methods) |

---

## Module Reference

### `cast.pipeline.run(input_file, output_file, *, verbose)`

Top-level function.  Orchestrates all stages.  Returns the resolved
`pathlib.Path` of the written JSON file.

### `cast.file_reader.read_source_file(path)`

Returns a `SourceFile(path, content, lines)` named-tuple.
Raises `FileReadError` on I/O problems.

### `cast.language_detector.detect_language(path)`

Returns a canonical language string (e.g. `"typescript"`).
Raises `UnsupportedLanguageError` for unknown extensions.

### `cast.parsers.registry.get_parser(language)`

Returns the registered `BaseParser` for *language*.

### `cast.parsers.registry.register_parser(language, parser)`

Register (or override) a parser at runtime — useful for testing or
plugin-style extension.

### `cast.output_writer.write_chunks(chunks, language, source_path, output_path)`

Serialises `list[CodeChunk]` to JSON and returns the output path.

---

## How to Add a New Language Parser

Adding a new language takes **4 small steps**.  No existing code needs
to change.

### Step 1 — Create the parser file

```python
# cast/parsers/rust_parser.py
from cast.chunk_model import CodeChunk
from cast.file_reader import SourceFile
from cast.parsers.base_parser import BaseParser

class RustParser(BaseParser):
    language = "rust"

    def extract_chunks(self, source: SourceFile) -> list[CodeChunk]:
        chunks = []
        counter = 1
        for lineno, line in enumerate(source.lines, start=1):
            # Detect `fn`, `struct`, `impl`, `trait`, `enum` …
            if line.strip().startswith(("fn ", "pub fn ", "async fn ", "pub async fn ")):
                end_line = self._find_closing_brace(source.lines, lineno - 1)
                if end_line:
                    import re
                    m = re.search(r'\bfn\s+(\w+)', line)
                    name = m.group(1) if m else None
                    chunks.append(CodeChunk(
                        chunk_id=self.make_chunk_id(counter),
                        type="function",
                        name=name,
                        start_line=lineno,
                        end_line=end_line,
                        code=self.slice_lines(source.lines, lineno, end_line),
                    ))
                    counter += 1
        return chunks

    # Reuse the brace-tracking helper from BraceLanguageParser
    def _find_closing_brace(self, lines, start_idx):
        from cast.parsers.brace_language_parser import BraceLanguageParser
        tmp = BraceLanguageParser.__new__(BraceLanguageParser)
        tmp._comment_tokens = {"line": "//", "block_start": "/*", "block_end": "*/"}
        return tmp._find_closing_brace(lines, start_idx)
```

### Step 2 — Register it

Open `cast/parsers/registry.py` and add two lines:

```python
from cast.parsers.rust_parser import RustParser   # ← add this import

_REGISTRY: dict[str, BaseParser] = {
    ...
    "rust": RustParser(),                          # ← add this entry
}
```

### Step 3 — Register the file extension (if not already present)

Open `cast/language_detector.py` and add to `EXTENSION_MAP`:

```python
".rs": "rust",   # already present in the initial version
```

### Step 4 — Done ✓

```bash
python -m cast.pipeline  src/main.rs  chunks_output.json --verbose
```

---

## Running the Tests

```bash
# From the project root (where cast/ lives)
python run_tests.py
```

This will process all test files (Python, JS, TS, Go, Rust, Ruby, PHP) and write
the output JSON files. Expected output (per file):

```
[cAST] Reading  : cast/tests/order_service.py
[cAST] Lines    : 105
[cAST] Language : python
[cAST] Parser   : PythonParser
[cAST] Extracting chunks …
[cAST] Found    : 9 chunk(s)
[cAST] Writing  : out_python.json
[cAST] Done     : /…/out_python.json
[PASS] Successfully processed cast/tests/order_service.py -> /…/out_python.json
```
