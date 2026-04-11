# Prompt Builder — Stage 2 of the AI Refactoring Pipeline

Reads the `chunks_output.json` produced by **cAST (Stage 1)** and generates
a high-quality, structured LLM refactoring prompt for every code chunk.
Results are written to `outputs/prompts.json`.

---

## Project Structure

```
├── prompt_builder/               ← Current directory
│   ├── prompt_builder/           ← Package containing all program logic
│   │   ├── __init__.py
│   │   ├── build_prompts.py      ← Pipeline orchestrator + CLI
│   │   ├── prompt_templates.py   ← All template logic and the TemplateRegistry
│   │   ├── few_shot_loader.py    ← Loads and indexes few-shot examples
│   │   └── few_shot_examples.json← Before/after refactoring demonstrations
│   │
│   ├── output/                   ← Generated outputs live here
│   │   └── prompts.json
│   │
│   ├── AUDIT.md                  ← Quality and architecture audit
│   ├── LOG.md                    ← Project development history
│   └── LOGIC_MAP.md              ← Execution flow details
│
└── outputs/                      ← Legacy/Global output location (optional)
```

---

## How to Run

### As a CLI command

```bash
# From the project root  (where prompt_builder/ lives)

# Basic — uses default paths
python -m prompt_builder.build_prompts

# With explicit paths + verbose output
python -m prompt_builder.build_prompts \
    --input  cast/chunks_output.json \
    --output outputs/prompts.json    \
    --verbose
```

### As a Python library

```python
from prompt_builder.build_prompts import run

output_path = run(
    input_path  = "cast/chunks_output.json",
    output_path = "outputs/prompts.json",
    verbose     = True,
)
print(f"Prompts written to {output_path}")
```

---

## Output Format (`prompts.json`)

```json
{
  "file_name": "order_service.py",
  "language": "python",
  "total_prompts": 9,
  "generated_at": "2025-01-15T10:30:00+00:00",
  "prompts": [
    {
      "chunk_id": "chunk_4",
      "chunk_type": "method",
      "name": "create_order",
      "start_line": 33,
      "end_line": 53,
      "prompt": "You are an expert python engineer ...\n── Goals ──\n...\n── Original Code ──\n```python\n...\n```",
      "original_code": "def create_order(self, ...):\n    ..."
    }
  ]
}
```

---

## Prompt Anatomy

Every generated prompt contains five sections:

```
You are an expert {language} engineer ...
Refactor the {chunk_type} `{name}` while strictly preserving its functionality.

Context: [parent class, if method]
Location: lines X–Y of `filename`
Style guide: [language-specific conventions]

── Goals ────────────────────────────────────────────────────────────────
- [chunk-type-specific improvement goals]

── Constraints ──────────────────────────────────────────────────────────
- [shared constraints + chunk-type-specific extras]

── Original Code ────────────────────────────────────────────────────────
```{language}
[verbatim code]
```

── Instructions ─────────────────────────────────────────────────────────
Return ONLY the refactored code block.

── Few-Shot Example ─────────────────────────────────────────────────────   ← optional
BEFORE / AFTER demonstration
```

---

## Template System

`prompt_templates.py` contains a `TemplateRegistry` that resolves the
best-matching template function for any `(language, chunk_type)` pair.

**Resolution order:**

| Priority | Key                       | Meaning                         |
|----------|---------------------------|---------------------------------|
| 1        | `("python", "class")`     | Exact match                     |
| 2        | `("python", "*")`         | Language wildcard               |
| 3        | `("*",      "class")`     | Type wildcard ← current default |
| 4        | `("*",      "*")`         | Global default                  |

**Chunk-type-aware goals** — every chunk type gets its own tailored goal list:

| Chunk Type        | Goal Focus                                              |
|-------------------|---------------------------------------------------------|
| `class`           | Structure, docstrings, attribute naming, method ordering|
| `function`        | Naming, docstring, magic values, signature clarity      |
| `async_function`  | Same as function + async idiom correctness              |
| `method`          | Single responsibility, naming, docstring                |
| `interface`       | Contract clarity, ISP, documentation                    |
| `struct`          | Field naming, grouping, documentation                   |
| `constructor`     | Param naming, validation, initialization clarity        |

**Chunk-type-aware constraints** — extra constraints are appended per type:

| Chunk Type        | Extra Constraint                                        |
|-------------------|---------------------------------------------------------|
| `class`           | Do NOT alter the class hierarchy or base classes        |
| `interface`       | Do NOT remove or reorder interface method signatures    |
| `async_function`  | Do NOT change the async/sync nature of the function     |
| `async_method`    | Do NOT change the async/sync nature of the method       |
| `constructor`     | Do NOT change the constructor's parameter list          |

---

## Few-Shot Examples

`few_shot_examples.json` contains 7 before/after refactoring demonstrations
covering Python, JavaScript, TypeScript, Java, and Go.

When a matching example exists for a `(language, chunk_type)` pair, it is
automatically appended to the prompt as a concrete quality target.

---

## How to Add a New Template

### Option A — Add a type-specific template

1. Write a new builder function in `prompt_templates.py`:

```python
def build_enum_prompt(ctx: PromptContext) -> str:
    return textwrap.dedent(f"""
        You are an expert {ctx.language} engineer refactoring an enum definition.
        ...
    """).rstrip()
```

2. Register it at the bottom of `_register_defaults()`:

```python
self.register("*", "enum", build_enum_prompt)
```

### Option B — Add a language+type-specific template

```python
self.register("go", "struct", build_go_struct_prompt)
```

### Option C — Register at runtime (no source change needed)

```python
from prompt_builder.prompt_templates import template_registry, build_standard_prompt

def my_rust_fn_prompt(ctx):
    ...

template_registry.register("rust", "function", my_rust_fn_prompt)
```

---

## How to Add New Few-Shot Examples

Open `few_shot_examples.json` and append to the `"examples"` array:

```json
{
  "id": "fs_rust_function_01",
  "language": "rust",
  "chunk_type": "function",
  "description": "Add doc comment, improve naming",
  "before": "fn f(x: i32) -> i32 { x * x }",
  "after": "/// Returns the square of `value`.\nfn square(value: i32) -> i32 {\n    value * value\n}",
  "notes": "Added rustdoc comment, renamed parameter."
}
```

The loader picks it up automatically on the next run — no code changes required.
