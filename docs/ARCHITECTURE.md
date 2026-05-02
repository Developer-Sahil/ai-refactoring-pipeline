---

## 🎨 1. Detailed Architecture Workflow

```mermaid
graph TD
    subgraph "Stage 1: cAST (Deconstruction)"
        A[Input .py Source] --> B[AST Tree Parsing]
        B --> C{Chunk Detection}
        C -->|Class/Method| D[Extract Code Segment]
        C -->|Function| D
        D --> F[chunks_output.json]
    end

    subgraph "Stage 2: Prompt Builder (Transformation)"
        F --> G[Load Full File Context]
        G --> H[Template Injection]
        H --> I[Persona: Senior Architect]
        I --> K[prompts.json]
    end

    subgraph "Stage 3: LLM Agent (Execution)"
        K --> L[Nested Chunk Filter]
        L --> M[Gemma 3 Family API (1B-27B)]
        M --> P[Bottom-Up Code Reassembly]
        P --> Q[Output .refactored.py]
    end

    subgraph "Stage 3.5: Auto-Fix (Linting)"
        Q --> Q1[Ruff Linting/Formatting]
        Q1 --> Q2[PEP 8 Cleanup]
    end

    subgraph "Stage 4: Validator (Verification)"
        Q --> V1[Syntax Validation]
        V1 --> V2[AST Integrity Comparison]
        V2 --> V3[Functional Validation]
        V3 --> V3A[Behavior Capture]
        V3 --> V3B[Property Testing]
        V3 --> V3C[Replay Execution]
        V3C --> W[validation_report.json]
    end

    subgraph "Infrastructure"
        R[llm_client.py] -.-> N[Gemma 3 Family]
        T[Global Context Block] -.-> M
    end
```

---

## 🚀 2. Recent Quality Enhancements

### 1. Global Architectural Awareness
*   **Context Injection**: Every prompt now includes the **entire source file** inside a `Global Architectural Context` block.
*   **Result**: The LLM understands all class/function dependencies and global variables before modifying a specific chunk, preventing broken references and ensuring consistent naming across the file.

### 2. High-Confidence "Senior Architect" Persona
*   **Standardization**: Transformed the default persona from a generic "AI Coder" to a "Senior Software Architect specializing in code renovation."
*   **Focus Areas**: Code readability (Clean Code), comprehensive documentation (Docstrings, JSDoc), Single Responsibility Principle (SRP), and strict type hinting (Python 3.9+).

### 3. Fault-Tolerant Reassembly (Nested Filtering)
*   **Strategy**: To prevent file corruption when refactoring nested methods, the agent now calculates the "Inclusivity Scope" for every prompt. 
*   **Rule**: If `Chunk A` is contained within `Chunk B`, its prompt is automatically skipped during execution, as the parent's refactoring inherently includes the child.

### 4. Transition to Gemma 3 Family
*   **Reasoning**: Upgraded the core engine to the `Gemma 3` family (1B, 4B, 12B, 27B) to provide a spectrum of reasoning capabilities. Higher parameter models are used for complex architectural transformations, while 1B ensures speed for documentation-only tasks.

### 4.5 Automated Style Enforcement (Stage 3.5)
*   **Linting**: Integrated `ruff` (format and fix) into the pipeline lifecycle.
*   **Benefit**: Ensures that all refactored output is PEP 8 compliant and free from common linting regressions before reaching the validator.

### 5. Automated Validation Gate (Stage 4)
*   **Syntax & AST**: Verifies compilation correctness and structural integrity.
*   **Functional Parity**: New suite of testing tools:
    - **Behavior Capture**: Records state changes.
    - **Property Testing**: Uses `input_generator.py` for edge-case coverage.
    - **Replay**: Executes tests against refactored code to ensure 100% logic preservation.
*   **Report Generation**: Produces a comprehensive `validation_report.json` for CI/CD integration.

---

## ⚙️ 3. Backend Infrastructure (SaaS Layer)

### 1. FastAPI Integration
*   **Rest API**: The core orchestrator is wrapped in a **FastAPI** application, exposing endpoints for job submission, status tracking, and result retrieval.
*   **Job Queue**: Implements an asynchronous processing queue using `ThreadPoolExecutor` and an in-memory `JobStore`. This ensures that large refactoring tasks do not block the API worker threads or cause HTTP timeouts.

### 2. Real-Time Communication
*   **WebSockets**: Utilizes bidirectional WebSocket connections to stream pipeline progress (Stage 1 ➔ 4) directly to the frontend.
*   **Polling Fallback**: The frontend is equipped with a polling mechanism to ensure status updates are received even if WebSocket connections are interrupted.

### 3. Scalable File Handling
*   **Isolated Workspaces**: Every job is assigned a unique UUID. Input files are staged in `backend/input/uploads/{job_id}/` and results are written to `backend/output/{job_id}/`. This ensures complete data isolation and allows the system to handle hundreds of concurrent jobs without state leakage.
*   **Archive Processing**: Automatic extraction and recursive processing of `.zip` uploads and folder-pickers.

---

## 💻 4. Frontend Presentation Layer (SaaS Dashboard)

### 1. Technology Stack
*   **Framework**: React (Bootstrapped via Vite with `--template react`).
*   **Styling**: Pure CSS (`index.css` and `App.css`) mapping explicitly to dynamic UI components.

### 2. Design System
*   **Paradigm**: **Light Mode Neumorphism / Skeuomorphism**.
*   **Physics**: Components leverage soft, deeply layered drop shadows (`--neumorphic-raised`) and inset inner shadows (`--neumorphic-inset`) spanning across a light monochromatic base (`#e0e5ec`). This conveys physicality, tactile touchpoints, and intuitive interaction zones entirely via CSS variables.

### 3. Core Interface Components
*   **Upload Context Zone**: A depressed tray that accepts file dragging, allowing intuitive staging of the "messy" source files.
*   **Settings Dial/Console**: Raised hardware-like toggle-switches, dial sliders, and configuration selectors directly mapping to the Backend Pipeline’s CLI arguments (`batch-size`, `delay`, `model`, `in-place`).
*   **Execution Controller**: A tactile Primary "Run Pipeline" hardware button which dynamically transitions via an embedded pipeline tracking sequence (Stage 1➔4) reflecting backend orchestrator tasks.
*   **Validation Viewer**: Emulated terminal/code well extracting `.refactored.py` output syntax dynamically into view for instant side-by-side human validation.

---

## 🛑 4. Known Constraints & Future Roadmap
*   **Top-Level Logic**: Code residing in the global script scope (no function/class) is currently skipped.
*   **Semantic Verification**: Future versions will implement logic-consistency checks to ensure the LLM hasn't changed the *observable behavior* of the code.
