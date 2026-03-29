---

## 🎨 4. Detailed Architecture Workflow

```mermaid
graph TD
    subgraph "Stage 1: cAST (Deconstruction)"
        A[Input .py Source] --> B[AST Tree Parsing]
        B --> C{Chunk Detection}
        C -->|Class/Method| D[Extract Code Segment]
        C -->|Function| D
        C -->|Nested Chunks| E[Mark Relationship]
        D --> F[chunks_output.json]
    end

    subgraph "Stage 2: Prompt Builder (Transformation)"
        F --> G[Load Full File Context]
        G --> H[Template Injection]
        H --> I[Persona: Senior Architect]
        I --> J[Inject Few-Shot Examples]
        J --> K[prompts.json]
    end

    subgraph "Stage 3: LLM Agent (Execution)"
        K --> L[Nested Chunk Filter]
        L --> M[Batched/Individual Prompt]
        M --> N[Gemini 2.5 Flash API]
        N --> O[XML Delimiter Parsing]
        O --> P[Bottom-Up Code Reassembly]
        P --> Q[Output .refactored.py]
    end

    subgraph "Infrastructure"
        R[llm_client.py] -.->|Retry Logic| N
        S[Exponential Backoff] -.-> R
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
*   **Reasoning**: Upgraded the core engine to `gemini-2.5-flash` to leverage its superior reasoning capabilities and high token limits, allowing for massive "Global Context" prompts without sacrificing performance.

---

## 🛑 6. Known Constraints & Future Roadmap
*   **Top-Level Logic**: Codes residing in the global script scope (no function/class) are currently skipped. **Mitigation**: Future cAST versions will treat the remainder of the file as an "Orphan Chunk."
*   **Syntax Validation**: Currently relies on the LLM's accuracy. **Future**: Integrate `ruff` or `flake8` as post-processing "Linter Stage."
