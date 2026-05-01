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
    Output --> Stage4[Stage 4: Validator]
    Stage4 --> Report[Validation Report]
```

---

## 📁 Project Structure

*   **/backend**: All backend code, including the refactoring pipeline.
    *   **/input**: Place the source files or "messy" codebases to be refactored here.
    *   **/pipeline**: Core modules (cAST, Prompt Builder, LLM Agent, Validator).
    *   **/output**: Auto-generated intermediate and final refactored files.
    *   **orchestrate.py**: Entry point to run the pipeline.
*   **/frontend**: React + Vite SaaS UI Dashboard utilizing a Light Mode Neumorphism design system.
*   **/docs**: Comprehensive project documentation and system design.
*   **docker-compose.ymal**: Deployment configuration.
*   **README.md**: Project overview and quick start.
*   **LOG.md**: Project change history.

---

## 🚀 Getting Started

The easiest way to run the pipeline is using the orchestrator:

### Python Backend

```bash
# Refactor a file in the input directory
python backend/orchestrate.py backend/input/order_service.py
```

### React Frontend Dashboard

```bash
cd frontend
npm install
npm run dev
```

### Advanced Processing Options

```bash
# Refactor an entire directory (batch mode)
python backend/orchestrate.py backend/input/

# Use batching to save API Quota (RPD)
python backend/orchestrate.py backend/input/order_service.py --batch-size 5

# Control request throttling
python backend/orchestrate.py backend/input/order_service.py --delay 10.0

# Specify an LLM model and refactor in-place
python backend/orchestrate.py backend/input/order_service.py --model gemini-2.0-flash --in-place
```

---

## ⚡ API Quota Optimization

To survive strict free-tier limits (e.g., **20 Requests Per Day**), the pipeline implements two key features:
1.  **Batching**: Combines multiple functions into one prompt to minimize RPD usage.
2.  **Server-Aware Throttling**: Automatically parses `retryDelay` from API errors and waits precisely the time required by the server.

---

## 📜 Project Documentation

*   **General History**: [LOG.md](file:///c:/dev/SDP/LOG.md)
*   **System Design (HLD/LLD)**: [docs/ARCHITECTURE.md](file:///c:/dev/SDP/docs/ARCHITECTURE.md)
*   **Project Audit**: [docs/AUDIT.md](file:///c:/dev/SDP/docs/AUDIT.md)
*   **Failure & Mitigation**: [docs/failure_and_mitigation_strategies.md](file:///c:/dev/SDP/docs/failure_and_mitigation_strategies.md)
*   **Stage 1 - cAST**: [backend/pipeline/cast/README.md](file:///c:/dev/SDP/backend/pipeline/cast/README.md)
*   **Stage 2 - Prompt Builder**: [backend/pipeline/prompt_builder/README.md](file:///c:/dev/SDP/backend/pipeline/prompt_builder/README.md)
*   **Stage 3 - LLM Agent**: [backend/pipeline/llm_agent/README.md](file:///c:/dev/SDP/backend/pipeline/llm_agent/README.md)
*   **Stage 4 - Validator**: [backend/pipeline/validator/README.md](file:///c:/dev/SDP/backend/pipeline/validator/README.md)

