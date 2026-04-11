---

## 🎨 4. Detailed Architecture Workflow

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
        L --> M[Gemini 2.5 Flash API]
        M --> P[Bottom-Up Code Reassembly]
        P --> Q[Output .refactored.py]
    end

    subgraph "Stage 4: Validator (Verification)"
        Q --> V1[Syntax Validation]
        V1 --> V2[AST Integrity Comparison]
        V2 --> V3[PEP8 Linting Check]
        V3 --> W[validation_report.txt]
    end

    subgraph "Infrastructure"
        R[llm_client.py] -.-> N[Gemini 2.5 Flash API]
        T[Global Context Block] -.-> M
    end
```

---

## 🚀 5. Recent Quality Enhancements

### 1. Global Architectural Awareness
*   **Context Injection**: Every prompt now includes the **entire source file** inside a `Global Architectural Context` block.
*   **Result**: The LLM understands all class/function dependencies and global variables before modifying a specific chunk, preventing broken references and ensuring consistent naming across the file.

### 2. High-Confidence "Senior Architect" Persona
*   **Standardization**: Transformed the default persona from a generic "AI Coder" to a "Senior Software Architect specializing in code renovation."
*   **Focus Areas**: Code readability (Clean Code), comprehensive documentation (Docstrings, JSDoc), Single Responsibility Principle (SRP), and strict type hinting (Python 3.9+).

### 3. Fault-Tolerant Reassembly (Nested Filtering)
*   **Strategy**: To prevent file corruption when refactoring nested methods, the agent now calculates the "Inclusivity Scope" for every prompt. 
*   **Rule**: If `Chunk A` is contained within `Chunk B`, its prompt is automatically skipped during execution, as the parent's refactoring inherently includes the child.

### 4. Transition to Gemini 2.5 Flash
*   **Reasoning**: Upgraded the core engine to `gemini-2.5-flash` to leverage its superior reasoning capabilities and high token limits.

### 5. Automated Validation Gate (Stage 4)
*   **Syntax & Linting**: Integrated a multi-tier validation stage that runs after every refactoring to verify syntax correctness, AST integrity, and PEP8 compliance.
*   **Report Generation**: Produces a `validation_report.txt` and optional JSON report for automated CI/CD integration.

---

## 🛑 6. Known Constraints & Future Roadmap
*   **Top-Level Logic**: Code residing in the global script scope (no function/class) is currently skipped.
*   **Semantic Verification**: Future versions will implement logic-consistency checks to ensure the LLM hasn't changed the *observable behavior* of the code.
