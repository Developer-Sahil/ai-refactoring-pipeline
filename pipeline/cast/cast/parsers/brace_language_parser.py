"""
cast.parsers.brace_language_parser
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
A robust AST-style parser for brace-delimited languages (JavaScript,
TypeScript, Java, C, C++, Go).

Strategy
--------
1. Scan every line with language-specific regex patterns to find the
   *start* of a structural unit (function, class, interface, etc.).
2. From that line, walk forward counting ``{`` / ``}`` to find the
   matching closing brace — i.e. ``end_line``.
3. Emit a :class:`~cast.chunk_model.CodeChunk` for each unit found.

This approach does not require any external library and handles the vast
majority of real-world source files.  Edge cases (e.g. braces inside
string literals or multi-line comments) are handled via a lightweight
token-state machine that skips over strings and comments.

Extending to a new brace-based language
----------------------------------------
Add an entry to :data:`LANGUAGE_PATTERNS` with:
  * A list of ``(chunk_type, compiled_regex)`` tuples.  Each regex must
    contain at least a named capture group ``name`` (the identifier) when
    applicable, or may omit it for anonymous constructs.
  * Optionally add line-comment and block-comment prefixes/delimiters to
    :data:`LANGUAGE_COMMENT_TOKENS`.
"""

from __future__ import annotations

import re
from typing import Optional

from cast.chunk_model import CodeChunk
from cast.file_reader import SourceFile
from cast.parsers.base_parser import BaseParser


# ---------------------------------------------------------------------------
# Per-language regex patterns
# Each tuple: (chunk_type_string, compiled_regex)
# The regex should match the line that BEGINS the construct.
# Named groups used: ``name`` (identifier), optional ``modifier``.
# ---------------------------------------------------------------------------

_JS_TS_PATTERNS = [
    # class Foo / export class Foo / abstract class Foo
    ("class", re.compile(
        r"^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+(?P<name>\w+)"
    )),
    # interface IFoo  (TypeScript)
    ("interface", re.compile(
        r"^\s*(?:export\s+)?interface\s+(?P<name>\w+)"
    )),
    # type Foo = { ... }  (TypeScript type alias with object body)
    ("type_alias", re.compile(
        r"^\s*(?:export\s+)?type\s+(?P<name>\w+)\s*=\s*\{"
    )),
    # function foo(  /  export function foo(  /  async function foo(
    ("function", re.compile(
        r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*(?P<name>\w+)\s*[(<]"
    )),
    # const/let/var foo = function(  /  const foo = async (  /  const foo = () =>
    ("function", re.compile(
        r"^\s*(?:export\s+)?(?:const|let|var)\s+(?P<name>\w+)\s*=\s*(?:async\s+)?(?:function\b|\([^)]*\)\s*=>|\w+\s*=>)"
    )),
    # Method shorthand inside class:  methodName(  /  async methodName(  /  get prop(
    ("method", re.compile(
        r"^\s*(?:(?:static|async|get|set|public|private|protected|override|readonly)\s+)*(?P<name>\w+)\s*\([^)]*\)\s*(?::\s*\S+\s*)?\{"
    )),
]

_JAVA_PATTERNS = [
    ("class", re.compile(
        r"^\s*(?:(?:public|private|protected|abstract|final|static)\s+)*class\s+(?P<name>\w+)"
    )),
    ("interface", re.compile(
        r"^\s*(?:(?:public|private|protected|abstract)\s+)*interface\s+(?P<name>\w+)"
    )),
    ("enum", re.compile(
        r"^\s*(?:(?:public|private|protected)\s+)*enum\s+(?P<name>\w+)"
    )),
    # Constructor: public ClassName(
    ("constructor", re.compile(
        r"^\s*(?:public|private|protected)\s+(?P<name>[A-Z]\w*)\s*\("
    )),
    # Method: <modifiers> <return_type> methodName(
    ("method", re.compile(
        r"^\s*(?:(?:public|private|protected|static|final|synchronized|abstract|native|default|override)\s+)+"
        r"(?:[\w<>\[\],\s]+?)\s+(?P<name>[a-z_]\w*)\s*\("
    )),
]

_C_CPP_PATTERNS = [
    ("struct", re.compile(
        r"^\s*(?:typedef\s+)?struct\s+(?P<name>\w+)?\s*\{"
    )),
    ("class", re.compile(          # C++ only
        r"^\s*class\s+(?P<name>\w+)"
    )),
    ("namespace", re.compile(      # C++ only
        r"^\s*namespace\s+(?P<name>\w+)\s*\{"
    )),
    # function definition: return_type funcname(
    ("function", re.compile(
        r"^(?!.*\bif\b)(?!.*\bfor\b)(?!.*\bwhile\b)(?!.*\bswitch\b)"
        r"[\w:*&<>\[\]\s]+?\s+(?P<name>[a-zA-Z_]\w*)\s*\([^;]*\)\s*(?:const\s*)?\{"
    )),
]

_GO_PATTERNS = [
    # func (receiver) FuncName(  or  func FuncName(
    ("function", re.compile(
        r"^\s*func\s+(?:\([^)]+\)\s+)?(?P<name>\w+)\s*[(\[]"
    )),
    # type Foo struct {  /  type Foo interface {
    ("struct", re.compile(
        r"^\s*type\s+(?P<name>\w+)\s+struct\s*\{"
    )),
    ("interface", re.compile(
        r"^\s*type\s+(?P<name>\w+)\s+interface\s*\{"
    )),
]

LANGUAGE_PATTERNS: dict[str, list[tuple[str, re.Pattern]]] = {
    "javascript": _JS_TS_PATTERNS,
    "typescript": _JS_TS_PATTERNS,
    "java":       _JAVA_PATTERNS,
    "c":          _C_CPP_PATTERNS,
    "cpp":        _C_CPP_PATTERNS,
    "go":         _GO_PATTERNS,
}

# ---------------------------------------------------------------------------
# Comment tokens  (used by the brace-counting state machine to skip braces
# inside comments)
# ---------------------------------------------------------------------------

LANGUAGE_COMMENT_TOKENS: dict[str, dict] = {
    "javascript": {"line": "//", "block_start": "/*", "block_end": "*/"},
    "typescript": {"line": "//", "block_start": "/*", "block_end": "*/"},
    "java":       {"line": "//", "block_start": "/*", "block_end": "*/"},
    "c":          {"line": "//", "block_start": "/*", "block_end": "*/"},
    "cpp":        {"line": "//", "block_start": "/*", "block_end": "*/"},
    "go":         {"line": "//", "block_start": "/*", "block_end": "*/"},
}


class BraceLanguageParser(BaseParser):
    """
    Parser for brace-delimited languages.

    Instantiate with a language identifier that exists in
    :data:`LANGUAGE_PATTERNS`.
    """

    def __init__(self, language: str) -> None:
        if language not in LANGUAGE_PATTERNS:
            raise ValueError(f"No patterns registered for language '{language}'")
        self.language = language
        self._patterns   = LANGUAGE_PATTERNS[language]
        self._comment_tokens = LANGUAGE_COMMENT_TOKENS.get(language, {})

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def extract_chunks(self, source: SourceFile) -> list[CodeChunk]:
        lines  = source.lines
        chunks : list[CodeChunk] = []
        counter = 1
        # Track which lines are already covered to avoid duplicate nesting
        covered_ends: list[tuple[int, int]] = []

        for lineno, line in enumerate(lines, start=1):  # lineno is 1-based
            chunk_type, name = self._match_line(line)
            if chunk_type is None:
                continue

            # Find the closing brace
            end_line = self._find_closing_brace(lines, lineno - 1)  # 0-based start
            if end_line is None:
                continue  # malformed block — skip

            # Skip if this range is entirely contained in an already-found chunk
            # (avoids double-emitting methods that were already caught by a broader pattern)
            if self._is_nested(lineno, end_line, covered_ends):
                continue

            code = self.slice_lines(lines, lineno, end_line)
            chunk = CodeChunk(
                chunk_id=self.make_chunk_id(counter),
                type=chunk_type,
                name=name,
                start_line=lineno,
                end_line=end_line,
                code=code,
            )
            chunks.append(chunk)
            covered_ends.append((lineno, end_line))
            counter += 1

        # Sort by start_line and re-number
        chunks.sort(key=lambda c: c.start_line)
        for i, chunk in enumerate(chunks, start=1):
            chunk.chunk_id = self.make_chunk_id(i)

        return chunks

    # ------------------------------------------------------------------ #
    # Pattern matching                                                     #
    # ------------------------------------------------------------------ #

    def _match_line(self, line: str) -> tuple[Optional[str], Optional[str]]:
        """Return (chunk_type, name) for the first matching pattern, or (None, None)."""
        for chunk_type, pattern in self._patterns:
            m = pattern.match(line)
            if m:
                try:
                    name = m.group("name")
                except IndexError:
                    name = None
                return chunk_type, name
        return None, None

    # ------------------------------------------------------------------ #
    # Brace-balanced end-line finder                                      #
    # ------------------------------------------------------------------ #

    def _find_closing_brace(self, lines: list[str], start_idx: int) -> Optional[int]:
        """
        Starting from *start_idx* (0-based), walk forward counting braces
        and return the 1-based line number of the line containing the
        matching closing ``}``.

        A lightweight state machine skips characters inside:
          * single-quoted strings
          * double-quoted strings
          * template literals (backtick)
          * line comments
          * block comments
        """
        depth        = 0
        in_string    = None   # None | '"' | "'" | '`'
        in_block_comment = False
        found_open   = False

        line_comment  = self._comment_tokens.get("line", "//")
        block_start   = self._comment_tokens.get("block_start", "/*")
        block_end     = self._comment_tokens.get("block_end", "*/")

        for idx in range(start_idx, len(lines)):
            line = lines[idx]
            i    = 0
            while i < len(line):
                ch = line[i]

                # ---- inside block comment ----
                if in_block_comment:
                    if line[i:i+len(block_end)] == block_end:
                        in_block_comment = False
                        i += len(block_end)
                    else:
                        i += 1
                    continue

                # ---- inside string ----
                if in_string:
                    if ch == "\\" and in_string != "`":
                        i += 2          # skip escaped character
                        continue
                    if ch == in_string:
                        in_string = None
                    i += 1
                    continue

                # ---- check for block comment start ----
                if line[i:i+len(block_start)] == block_start:
                    in_block_comment = True
                    i += len(block_start)
                    continue

                # ---- check for line comment ----
                if line[i:i+len(line_comment)] == line_comment:
                    break   # rest of line is a comment — stop processing

                # ---- check for string opening ----
                if ch in ('"', "'", "`"):
                    in_string = ch
                    i += 1
                    continue

                # ---- brace counting ----
                if ch == "{":
                    depth += 1
                    found_open = True
                elif ch == "}":
                    if found_open:
                        depth -= 1
                        if depth == 0:
                            return idx + 1   # convert to 1-based

                i += 1

        return None  # never found closing brace

    # ------------------------------------------------------------------ #
    # Nesting guard                                                        #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _is_nested(
        start: int,
        end: int,
        covered: list[tuple[int, int]],
    ) -> bool:
        """Return True if [start, end] is fully contained within any covered range."""
        return any(s <= start and end <= e for s, e in covered)
