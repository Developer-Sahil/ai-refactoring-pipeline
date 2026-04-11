"""
prompt_builder.prompt_templates
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
All prompt-construction logic lives here.

Design decisions
----------------
* Templates are plain Python — no Jinja2 dependency needed.
* Each public function accepts a ``PromptContext`` dataclass and returns
  a fully-rendered string.
* A ``TemplateRegistry`` maps (language, chunk_type) → builder function,
  falling back through a chain:
    (language, chunk_type) → (language, "*") → ("*", chunk_type) → default
* Adding a new template = one function + one registry.register() call.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass, field
from typing import Callable, Optional


# ── Shared goal / constraint copy ────────────────────────────────────────────

_GOALS_BY_CHUNK_TYPE: dict[str, list[str]] = {
    "class": [
        "Improve class and attribute naming to reflect their purpose clearly (intent-revealing names)",
        "Add comprehensive docstrings following language conventions (e.g., PEP 257 for Python)",
        "Ensure the class has a single, well-defined responsibility (Single Responsibility Principle)",
        "Simplify complex methods — extract helpers where appropriate",
        "Ensure consistent use of access modifiers and visibility conventions",
        "Improve readability and maintainability of the overall class structure",
        "Add inline comments to explain complex or non-obvious internal logic",
    ],
    "function": [
        "Improve function and parameter naming to express intent clearly",
        "Add comprehensive docstrings summarizing purpose, parameters, and return values",
        "Simplify conditional logic and reduce nesting (e.g., using guard clauses)",
        "Replace magic numbers or strings with named constants or configuration",
        "Improve readability without altering the function signature",
        "Ensure proper error handling and input validation (Fail-Fast principle)",
        "Add type hints/annotations where applicable (e.g., Python 3.9+)",
        "Preserve and enhance internal comments that explain 'why' instead of 'what'",
    ],
    "async_function": [
        "Improve function and parameter naming to express intent clearly",
        "Add comprehensive docstrings including async behavior details",
        "Ensure async/await usage is idiomatic and error-handling is robust (try/except blocks)",
        "Simplify conditional logic and reduce nesting where possible",
        "Replace magic numbers or strings with named constants",
        "Add type hints/annotations where applicable",
        "Optimize for concurrency where obvious (avoid unnecessary sequential awaits)",
    ],
    "method": [
        "Improve method and parameter naming to express intent clearly",
        "Add descriptive docstrings summarizing purpose and return values",
        "Simplify conditional logic and reduce nesting using guard clauses",
        "Ensure the method has a single, clear responsibility (SRP)",
        "Improve readability without altering the method signature",
        "Add type hints/annotations where applicable",
        "Preserve and enhance internal comments that explain complex logic",
    ],
    "async_method": [
        "Improve method and parameter naming to express intent",
        "Add comprehensive docstrings summarizing purpose and async behavior",
        "Ensure async/await usage is idiomatic and error-handling is robust",
        "Simplify conditional logic and reduce nesting where possible",
        "Ensure the method has a single, clear responsibility",
        "Add type hints/annotations where applicable",
    ],
    "interface": [
        "Improve interface and method naming to express their contract clearly",
        "Add comprehensive documentation for method signatures and expected behavior",
        "Ensure the interface follows the Interface Segregation Principle",
        "Make the interface easier to implement and understand",
    ],
    "struct": [
        "Improve field naming to reflect the data each field holds precisely",
        "Add field-level documentation explaining units, ranges, or usage",
        "Group related fields logically to improve cohesion",
        "Ensure naming follows language conventions",
        "Add type hints/annotations where applicable",
    ],
    "enum": [
        "Improve enum and member naming to be self-documenting",
        "Add documentation for the enum type and each individual member",
        "Ensure naming follows language conventions (e.g., UPPER_SNAKE for constants)",
    ],
    "constructor": [
        "Improve parameter naming and provide sensible default values",
        "Add comprehensive constructor docstrings",
        "Simplify initialization logic and ensure internal state is valid",
        "Ensure validation is clear and fails fast on bad input",
        "Add type hints/annotations where applicable",
    ],
    "namespace": [
        "Improve namespace organization and naming",
        "Add documentation for the namespace's purpose and contents",
        "Ensure public vs. private boundaries are clear and idiomatic",
    ],
    "module": [
        "Improve top-level naming, organization, and exports",
        "Add comprehensive module-level docstrings (purpose, usage examples)",
        "Simplify top-level logic and ensure clean initialization",
        "Improve imports organization (e.g., alphabetical, grouped)",
    ],
    # Fallback — used when chunk type is not in the map above
    "_default": [
        "Improve naming to be descriptive and intention-revealing",
        "Add comprehensive documentation and inline comments",
        "Simplify complex logic and reduce nesting where possible",
        "Replace magic values with named constants",
        "Improve readability, maintainability, and diagnostic clarity",
        "Follow Clean Code best practices (SOLID, DRY, KISS)",
    ],
}

_CONSTRAINTS_COMMON: list[str] = [
    "Do NOT change the observable behaviour of the code (Functional Parity)",
    "Do NOT rename public APIs, exported symbols, or method signatures",
    "Do NOT remove or reorder imports / dependencies unless they are unused",
    "Do NOT introduce new external dependencies",
    "Do NOT add new logic, features, or side-effects",
    "Preserve AND ENHANCE all existing comments that carry meaningful context",
    "Maintain the indentation style of the surrounding file",
    "Generated code must be syntactically correct and follow the provided style guide",
]

_CONSTRAINTS_BY_CHUNK_TYPE: dict[str, list[str]] = {
    "class":         ["Do NOT alter the class hierarchy or base classes"],
    "interface":     ["Do NOT remove or reorder interface method signatures"],
    "async_function":["Do NOT change the async/sync nature of the function"],
    "async_method":  ["Do NOT change the async/sync nature of the method"],
    "constructor":   ["Do NOT change the constructor's parameter list"],
}

_LANGUAGE_STYLE_NOTE: dict[str, str] = {
    "python":     "Follow PEP 8 and PEP 257 conventions.",
    "javascript": "Follow Airbnb / StandardJS style conventions where applicable.",
    "typescript": "Follow TypeScript best practices; prefer explicit types over `any`.",
    "java":       "Follow Oracle Java Code Conventions and Effective Java guidelines.",
    "c":          "Follow C89/C99 conventions; keep headers and implementations aligned.",
    "cpp":        "Follow C++ Core Guidelines; prefer modern C++17 idioms.",
    "go":         "Follow Effective Go and the Go style guide (gofmt-compatible output).",
}


# ── Context object passed to every builder ────────────────────────────────────

@dataclass
class PromptContext:
    """All information a template function needs to render a prompt."""

    chunk_id:    str
    chunk_type:  str               # e.g. "function", "class", "method"
    name:        Optional[str]     # identifier, may be None
    language:    str               # e.g. "python"
    code:        str               # verbatim source
    start_line:  int
    end_line:    int
    full_file_content: Optional[str] = None # Entire contents of the source file
    metadata:    dict = field(default_factory=dict)   # e.g. {"parent_class": "Foo"}

    # Derived helpers
    @property
    def display_name(self) -> str:
        return self.name or f"<anonymous {self.chunk_type}>"

    @property
    def line_range(self) -> str:
        return f"lines {self.start_line}–{self.end_line}"

    @property
    def goals(self) -> list[str]:
        return _GOALS_BY_CHUNK_TYPE.get(self.chunk_type, _GOALS_BY_CHUNK_TYPE["_default"])

    @property
    def constraints(self) -> list[str]:
        extras = _CONSTRAINTS_BY_CHUNK_TYPE.get(self.chunk_type, [])
        return _CONSTRAINTS_COMMON + extras

    @property
    def style_note(self) -> str:
        return _LANGUAGE_STYLE_NOTE.get(self.language, "Follow the conventions of the surrounding codebase.")

    @property
    def context_note(self) -> str:
        parent = self.metadata.get("parent_class")
        if parent:
            return f"This {self.chunk_type} is defined inside the `{parent}` class."
        return ""


# ── Template builders ─────────────────────────────────────────────────────────

def _bullet(items: list[str], indent: int = 0) -> str:
    pad = " " * indent
    return "\n".join(f"{pad}- {item}" for item in items)


def build_standard_prompt(ctx: PromptContext) -> str:
    """
    The default high-quality template.
    Suitable for functions, methods, classes, and most other chunk types.
    """
    context_line = f"\nContext: {ctx.context_note}\n" if ctx.context_note else ""

    template = textwrap.dedent("""
        ─ ─ Final Goal ───────────────────────────────────────────────────────────
        Transform this code into clean, well-documented, and industrial-grade software
        that follows modern system design principles (SOLID, DRY, KISS).

        ── Global Architectural Context ──────────────────────────────────────────
        The following is the full content of `{file_name}` for context:
        ```{language}
        {full_file_content}
        ```

        ── Target Chunk to Refactor ──────────────────────────────────────────────
        Chunk ID: {chunk_id}
        Type: {chunk_type}
        Name: {display_name}
        Location: {line_range}

        ── Original Chunk Code ──────────────────────────────────────────────────
        ```{language}
        {code}
        ```

        ── Goals ────────────────────────────────────────────────────────────────
        {goals}

        ── Constraints ──────────────────────────────────────────────────────────
        {constraints}

        ── Instructions ─────────────────────────────────────────────────────────
        Refactor ONLY the target chunk `{display_name}`. 
        Use the global context to ensure your changes are consistent with the rest of the file.
        Return ONLY the refactored code block for this specific chunk.
        Do not include explanations, markdown prose, or diff output.
        The returned code must be a drop-in replacement for the original chunk.
    """).strip()

    return template.format(
        language=ctx.language,
        chunk_type=ctx.chunk_type,
        display_name=ctx.display_name,
        context_line=context_line,
        line_range=ctx.line_range,
        file_name="{file_name}",
        style_note=ctx.style_note,
        goals=_bullet(ctx.goals),
        constraints=_bullet(ctx.constraints),
        code=ctx.code,
        full_file_content=ctx.full_file_content or "Not provided.",
        chunk_id=ctx.chunk_id
    )


def build_class_prompt(ctx: PromptContext) -> str:
    """
    Specialised template for class-level chunks.
    Emphasises structural clarity and documentation coverage.
    """
    context_line = f"\nContext: {ctx.context_note}\n" if ctx.context_note else ""

    template = textwrap.dedent("""\
        You are an expert {language} engineer performing a targeted class-level refactoring.
        Refactor the class `{display_name}` while strictly preserving its public interface and behaviour.
        {context_line}
        Location: {line_range} of `{file_name}`
        Language: {language}
        Style guide: {style_note}

        ── Goals ────────────────────────────────────────────────────────────────
        {goals}

        ── Constraints ──────────────────────────────────────────────────────────
        {constraints}

        ── Focus Areas ──────────────────────────────────────────────────────────
        - Class-level docstring: briefly describe purpose and responsibility (max 2 lines)
        - Method-level docstrings: briefly summarize what each method does (one line)
        - Attribute naming: ensure name clarity over verbose comments
        - Method ordering: constructors first, then public, then private/protected

        ── Original Code ────────────────────────────────────────────────────────
        ```{language}
        {code}
        ```

        ── Instructions ─────────────────────────────────────────────────────────
        Return ONLY the refactored class definition.
        Do not include explanations, markdown prose, or diff output.
        The returned class must be a drop-in replacement for the original.
    """).rstrip()

    return template.format(
        language=ctx.language,
        display_name=ctx.display_name,
        context_line=context_line,
        line_range=ctx.line_range,
        file_name="{file_name}",
        style_note=ctx.style_note,
        goals=_bullet(ctx.goals),
        constraints=_bullet(ctx.constraints),
        code=ctx.code
    )


def build_interface_prompt(ctx: PromptContext) -> str:
    """Specialised template for interface / protocol definitions."""
    template = textwrap.dedent("""\
        You are an expert {language} engineer reviewing an interface definition.
        Refactor the interface `{display_name}` to improve clarity and documentation.

        Location: {line_range} of `{file_name}`
        Language: {language}
        Style guide: {style_note}

        ── Goals ────────────────────────────────────────────────────────────────
        {goals}

        ── Constraints ──────────────────────────────────────────────────────────
        {constraints}

        ── Original Code ────────────────────────────────────────────────────────
        ```{language}
        {code}
        ```

        ── Instructions ─────────────────────────────────────────────────────────
        Return ONLY the refactored interface definition.
        Do not include explanations, markdown prose, or diff output.
    """).rstrip()

    return template.format(
        language=ctx.language,
        display_name=ctx.display_name,
        line_range=ctx.line_range,
        file_name="{file_name}",
        style_note=ctx.style_note,
        goals=_bullet(ctx.goals),
        constraints=_bullet(ctx.constraints),
        code=ctx.code
    )


# ── Registry ─────────────────────────────────────────────────────────────────

TemplateBuilderFn = Callable[[PromptContext], str]


class TemplateRegistry:
    """
    Maps (language, chunk_type) pairs to prompt-builder functions.

    Resolution order for a query (lang="python", type="method"):
      1. ("python",  "method")    — exact match
      2. ("python",  "*")         — language wildcard
      3. ("*",       "method")    — type wildcard
      4. ("*",       "*")         — global default

    Usage::

        registry = TemplateRegistry()
        builder  = registry.resolve("python", "class")
        prompt   = builder(ctx)
    """

    def __init__(self) -> None:
        self._map: dict[tuple[str, str], TemplateBuilderFn] = {}
        self._register_defaults()

    def register(
        self,
        language: str,
        chunk_type: str,
        builder: TemplateBuilderFn,
    ) -> None:
        """
        Register *builder* for the given *(language, chunk_type)* pair.
        Use ``"*"`` as a wildcard for either dimension.
        """
        self._map[(language.lower(), chunk_type.lower())] = builder

    def resolve(self, language: str, chunk_type: str) -> TemplateBuilderFn:
        """Return the best matching builder function."""
        lang = language.lower()
        ctype = chunk_type.lower()
        candidates = [
            (lang,  ctype),
            (lang,  "*"),
            ("*",   ctype),
            ("*",   "*"),
        ]
        for key in candidates:
            if key in self._map:
                return self._map[key]
        # Should never reach here if defaults are registered correctly
        return build_standard_prompt

    def _register_defaults(self) -> None:
        # Global default
        self.register("*",     "*",         build_standard_prompt)
        # Type-specific
        self.register("*",     "class",     build_class_prompt)
        self.register("*",     "interface", build_interface_prompt)
        # You can add language+type combos here, e.g.:
        #   self.register("go", "struct", build_go_struct_prompt)


# Module-level singleton — import this in build_prompts.py
template_registry = TemplateRegistry()


# ── Public helper ─────────────────────────────────────────────────────────────

def render_prompt(ctx: PromptContext, file_name: str) -> str:
    """
    Render the best-matching template for *ctx* and substitute ``{file_name}``.
    """
    builder = template_registry.resolve(ctx.language, ctx.chunk_type)
    raw     = builder(ctx)
    return raw.replace("{file_name}", file_name)


def build_batch_prompt(
    contexts: list[PromptContext], 
    file_name: str,
    few_shot_example: Optional[dict] = None
) -> str:
    """
    Template for refactoring multiple chunks in a single request.
    Use this to save API quota.
    """
    language = contexts[0].language
    style_note = contexts[0].style_note
    
    chunk_blocks = []
    for ctx in contexts:
        block = textwrap.dedent(f"""\
            ── Chunk: {ctx.chunk_id} ({ctx.chunk_type}: {ctx.display_name}) ──
            Location: {ctx.line_range}
            ```{language}
            {ctx.code}
            ```
        """)
        chunk_blocks.append(block)
        
    all_chunks_text = "\n\n".join(chunk_blocks)
    
    template = textwrap.dedent("""\
        ── Global Architectural Context ──────────────────────────────────────────
        The following is the full content of `{file_name}` for context:
        ```{language}
        {full_file_content}
        ```

        ── target Chunks to Refactor ─────────────────────────────────────────────
        Refactor the following {num_chunks} code chunks from `{file_name}`.

        ── Original Chunks ──────────────────────────────────────────────────────
        {all_chunks_text}

        ── Instructions ─────────────────────────────────────────────────────────
        For EACH chunk, return the refactored version wrapped in these exact delimiters:
        
        <chunk id="chunk_id_here">
        [Your refactored code for this chunk here]
        </chunk>

        Example format:
        <chunk id="chunk_1">
        def my_function():
            pass
        </chunk>
        
        Do not include any prose, explanations, or additional text outside these tags.
    """).rstrip()

    prompt = template.format(
        language=language,
        num_chunks=len(contexts),
        file_name=file_name,
        style_note=style_note,
        all_chunks_text=all_chunks_text,
        full_file_content=contexts[0].full_file_content or "Not provided."
    )

    if few_shot_example:
        separator = "\n\n── Few-Shot Example ─────────────────────────────────────────────────────"
        block = (
            f"{separator}\n"
            f"The following is an example of the quality and style of refactoring expected for individual chunks.\n\n"
            f"BEFORE:\n```{language}\n{few_shot_example['before']}\n```\n\n"
            f"AFTER:\n```{language}\n{few_shot_example['after']}\n```\n"
            f"Note: {few_shot_example.get('notes', '')}"
        )
        prompt += block

    return prompt
