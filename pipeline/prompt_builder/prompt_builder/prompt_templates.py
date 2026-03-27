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
        "Improve class and attribute naming to reflect their purpose clearly",
        "Add or improve docstrings at the class and method level",
        "Simplify complex methods — extract helpers where appropriate",
        "Ensure consistent use of access modifiers / visibility conventions",
        "Improve readability of the overall class structure",
    ],
    "function": [
        "Improve function and parameter naming to express intent",
        "Add or improve the docstring (purpose, args, returns, raises)",
        "Simplify conditional logic and reduce nesting where possible",
        "Replace magic numbers or strings with named constants",
        "Improve readability without altering the function signature",
    ],
    "async_function": [
        "Improve function and parameter naming to express intent",
        "Add or improve the docstring (purpose, args, returns, raises)",
        "Ensure async/await usage is idiomatic and error-handling is robust",
        "Simplify conditional logic and reduce nesting where possible",
        "Replace magic numbers or strings with named constants",
    ],
    "method": [
        "Improve method and parameter naming to express intent",
        "Add or improve the docstring (purpose, args, returns)",
        "Simplify conditional logic and reduce nesting where possible",
        "Ensure the method has a single, clear responsibility",
        "Improve readability without altering the method signature",
    ],
    "async_method": [
        "Improve method and parameter naming to express intent",
        "Add or improve the docstring (purpose, args, returns)",
        "Ensure async/await usage is idiomatic and error-handling is robust",
        "Simplify conditional logic and reduce nesting where possible",
        "Ensure the method has a single, clear responsibility",
    ],
    "interface": [
        "Improve interface and method naming to express their contract clearly",
        "Add or improve documentation for each method signature",
        "Ensure the interface follows the Interface Segregation Principle",
        "Make the interface easier to implement and understand",
    ],
    "struct": [
        "Improve field naming to reflect the data each field holds",
        "Add or improve struct-level and field-level documentation",
        "Group related fields logically",
        "Ensure naming follows language conventions",
    ],
    "enum": [
        "Improve enum and member naming to be self-documenting",
        "Add or improve documentation for the enum type and each member",
        "Ensure naming follows language conventions (UPPER_SNAKE for constants, etc.)",
    ],
    "constructor": [
        "Improve parameter naming and default values",
        "Add or improve the constructor docstring",
        "Simplify initialization logic where possible",
        "Ensure validation is clear and fails fast on bad input",
    ],
    "namespace": [
        "Improve namespace organisation and naming",
        "Add documentation for the namespace's purpose",
        "Ensure public vs. private boundaries are clear",
    ],
    "module": [
        "Improve top-level naming and organisation",
        "Add or improve module-level documentation",
        "Simplify top-level logic",
    ],
    # Fallback — used when chunk type is not in the map above
    "_default": [
        "Improve naming to be descriptive and intention-revealing",
        "Add or improve inline documentation",
        "Simplify complex logic and reduce nesting where possible",
        "Replace magic values with named constants",
        "Improve readability and maintainability",
    ],
}

_CONSTRAINTS_COMMON: list[str] = [
    "Do NOT change the observable behaviour of the code",
    "Do NOT rename public APIs, exported symbols, or method signatures",
    "Do NOT remove or reorder imports / dependencies",
    "Do NOT introduce new external dependencies",
    "Do NOT add new logic, features, or side-effects",
    "Preserve all existing comments that carry meaningful context",
    "Maintain the indentation style of the surrounding file",
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

    template = textwrap.dedent("""\
        You are an expert {language} engineer performing a targeted code refactoring.
        Refactor the {chunk_type} `{display_name}` while strictly preserving its functionality.
        {context_line}
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
        Return ONLY the refactored code block.
        Do not include explanations, markdown prose, or diff output.
        The returned code must be a drop-in replacement for the original.
    """).rstrip()

    return template.format(
        language=ctx.language,
        chunk_type=ctx.chunk_type,
        display_name=ctx.display_name,
        context_line=context_line,
        line_range=ctx.line_range,
        file_name="{file_name}", # Placeholder for replace in render_prompt()
        style_note=ctx.style_note,
        goals=_bullet(ctx.goals),
        constraints=_bullet(ctx.constraints),
        code=ctx.code
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
        - Class-level docstring: describe purpose, key responsibilities, and usage
        - Method-level docstrings: describe what each method does, params, and return value
        - Attribute naming: ensure each attribute name clearly communicates what it holds
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
