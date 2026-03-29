# AI-Powered Code Refactoring Pipeline

An end-to-end processing pipeline designed to ingest, chunk, and transform source code into high-quality, structured inputs for large language model (LLM) refactoring agents.

---

## 🏗️ High-Level Architecture

```mermaid
graph LR
    Source[Source Code File] --> Stage1[Stage 1: cAST]
    Stage1 --> Chunks[chunks_output.json]
    Chunks --> Stage2[Stage 2: Prompt Builder]
    Stage2 --> Prompts[prompts.json]
    Prompts --> Stage3[Stage 3: LLM Refactoring Agent]
    Stage3 --> Output[Refactored Code]
```

---

## 📁 Project Structure

*   **/input**: Place the source files or "messy" codebases to be refactored here $(e.g., `order_service.py`).
*   **/pipeline**: Contains the core modules of the refactoring engine:
    *   **[cAST](file:///c:/dev/SDP/pipeline/cast/)**: AST-based code chunking.
    *   **[Prompt Builder](file:///c:/dev/SDP/pipeline/prompt_builder/)**: Persona-driven prompt generation.
    *   **[LLM Agent](file:///c:/dev/SDP/pipeline/llm_agent/)**: Refactoring execution and file reconstruction.
*   **/output**: (Auto-generated) Stores intermediate JSON outputs (`chunks_output.json`, `prompts.json`) and final refactored files.
*   **[orchestrate.py](file:///c:/dev/SDP/orchestrate.py)**: The single entry point to run the entire pipeline end-to-end.

---

## 🚀 Getting Started

The easiest way to run the pipeline is using the orchestrator:

```bash
# Refactor a file in the input directory
python orchestrate.py input/order_service.py
```

### Advanced Processing Options

```bash
# Refactor an entire directory (batch mode)
python orchestrate.py input/

# Use batching to save API Quota (RPD)
# Processes 5 chunks in a single LLM request (default: 3)
python orchestrate.py input/order_service.py --batch-size 5

# Control request throttling (avoid 429 errors)
# Wait 10 seconds between each LLM call
python orchestrate.py input/order_service.py --delay 10.0

# Specify an LLM model and refactor in-place
python orchestrate.py input/order_service.py --model gemini-2.0-flash --in-place
```

---

## ⚡ API Quota Optimization

To survive strict free-tier limits (e.g., **20 Requests Per Day**), the pipeline implements two key features:
1.  **Batching**: Combines multiple functions into one prompt to minimize RPD usage.
2.  **Server-Aware Throttling**: Automatically parses `retryDelay` from API errors and waits precisely the time required by the server.

---

## 📜 Project Documentation

*   **General History**: [LOG.md](file:///c:/dev/SDP/LOG.md)
*   **System Design (HLD/LLD)**: [SYSTEM_DESIGN.md](file:///c:/dev/SDP/SYSTEM_DESIGN.md)
*   **Stage 1 - cAST**: [pipeline/cast/README.md](file:///c:/dev/SDP/pipeline/cast/README.md)
*   **Stage 2 - Prompt Builder**: [pipeline/prompt_builder/README.md](file:///c:/dev/SDP/pipeline/prompt_builder/README.md)
*   **Stage 3 - LLM Agent**: [pipeline/llm_agent/README.md](file:///c:/dev/SDP/pipeline/llm_agent/README.md)

