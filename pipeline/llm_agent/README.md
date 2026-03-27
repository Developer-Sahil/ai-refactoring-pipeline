# LLM Refactoring Agent — Stage 3 of the AI Refactoring Pipeline

Reads the `prompts.json` produced by **Prompt Builder (Stage 2)**, sends them to an LLM, parses the code out of the response, and integrates the refactored code back into the source file.

---

## Project Structure

```
project_root/
│
├── prompt_builder/               ← Stage 2 output lives here
│   └── output/prompts.json
│
├── llm_agent/                    ← This module
│   ├── llm_agent/
│   │   ├── __init__.py
│   │   ├── run_agent.py          ← Pipeline orchestrator + CLI
│   │   ├── llm_client.py         ← Interacts with google-genai API
│   │   ├── response_parser.py    ← Extracts code from LLM markdown
│   │   └── code_replacer.py      ← Re-writes source files with new chunks
│   │
│   ├── AUDIT.md                  ← Quality and architecture audit
│   ├── LOG.md                    ← Project development history
│   └── LOGIC_MAP.md              ← Execution flow details
```

---

## How to Run

### Prerequisites
You must have the `google-genai` library installed and a valid Gemini API key.
```bash
pip install google-genai
$env:GEMINI_API_KEY="your_api_key_here"
```

### As a CLI command

```bash
# From the project root

# Default completely safe mode (creates a .refactored copy)
python -m llm_agent.run_agent --input prompt_builder/output/prompts.json

# Dry run mode (read prompts, don't call LLM or write files)
python -m llm_agent.run_agent --input prompt_builder/output/prompts.json --dry-run

# In-place mode (WARNING: overwrites original source code)
python -m llm_agent.run_agent --input prompt_builder/output/prompts.json --in-place

# Custom Model selection
python -m llm_agent.run_agent --input prompt_builder/output/prompts.json --model gemini-2.5-pro
```

---

## Core Features

1. **Intelligent Processing Order**: The orchestrator reads chunks and applies them to the file in **reverse-line order** (bottom up). This prevents line-insertion/deletion math from corrupting the coordinates of chunks located higher up in the file.
2. **Safe By Default**: Run the agent. By default it will output `source_file.refactored.py` allowing you to perform a simple diff review before accepting the changes.
3. **Resilient API Calls**: `llm_client.py` uses exponential backoff to recover from transite rate limits (HTTP 429) or overloaded servers (HTTP 503).
4. **Resilient Parsing**: The `response_parser.py` aggressively hunts for standard markdown codeblocks, extracting *only* the code and ignoring conversational filler (e.g., "Here is the refactored answer...").
