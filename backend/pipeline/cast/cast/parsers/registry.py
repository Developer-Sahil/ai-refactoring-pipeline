"""
cast.parsers.registry
~~~~~~~~~~~~~~~~~~~~~
Central registry that maps language identifiers to parser instances.

Adding a new language parser
-----------------------------
1. Create ``cast/parsers/my_language_parser.py`` with a class that
   extends :class:`~cast.parsers.base_parser.BaseParser`.
2. Import it here.
3. Add one line to :data:`_REGISTRY`:

   .. code-block:: python

      "my_language": MyLanguageParser(),

That's it — the rest of the pipeline picks it up automatically.
"""

from __future__ import annotations
import logging
from typing import Optional

from cast.parsers.base_parser import BaseParser
from cast.parsers.python_parser import PythonParser

logger = logging.getLogger(__name__)


def _get_parser_with_fallback(language: str) -> Optional[BaseParser]:
    """
    Attempt to initialize the robust TreeSitterParser.
    Falls back to BraceLanguageParser if tree-sitter bindings are missing.
    Returns None if neither parser supports the language, so the registry
    can skip it cleanly instead of crashing at import time.
    """
    # ── Try tree-sitter first (most accurate) ────────────────────────────
    try:
        from cast.parsers.tree_sitter_parser import TreeSitterParser
        return TreeSitterParser(language)
    except (ImportError, ValueError) as e:
        logger.debug(f"TreeSitterParser unavailable for '{language}': {e}. Trying fallback.")

    # ── Fallback: regex + brace-balance heuristic ────────────────────────
    try:
        from cast.parsers.brace_language_parser import BraceLanguageParser
        return BraceLanguageParser(language)
    except (ImportError, ValueError) as e:
        logger.warning(
            f"No parser available for '{language}': {e}. "
            f"It will not appear in the supported-language list. "
            f"To add support, implement patterns in BraceLanguageParser "
            f"or install the tree-sitter-{language} binding."
        )
        return None


# ---------------------------------------------------------------------------
# Registry  ─  language_id → parser instance
# Languages whose _get_parser_with_fallback returns None are excluded.
# ---------------------------------------------------------------------------

_CANDIDATES: dict[str, Optional[BaseParser]] = {
    "python":     PythonParser(),
    "javascript": _get_parser_with_fallback("javascript"),
    "typescript": _get_parser_with_fallback("typescript"),
    "java":       _get_parser_with_fallback("java"),
    "c":          _get_parser_with_fallback("c"),
    "cpp":        _get_parser_with_fallback("cpp"),
    "go":         _get_parser_with_fallback("go"),
    "rust":       _get_parser_with_fallback("rust"),   # None until bindings/patterns added
    "ruby":       _get_parser_with_fallback("ruby"),   # None until bindings/patterns added
    "php":        _get_parser_with_fallback("php"),    # None until bindings/patterns added
}

# Filter out languages with no working parser
_REGISTRY: dict[str, BaseParser] = {
    lang: parser
    for lang, parser in _CANDIDATES.items()
    if parser is not None
}

logger.debug(f"Registered parsers: {sorted(_REGISTRY.keys())}")


def get_parser(language: str) -> BaseParser:
    """
    Return the registered parser for *language*.

    Raises
    ------
    KeyError
        If no parser has been registered for that language.
    """
    if language not in _REGISTRY:
        raise KeyError(
            f"No parser registered for language '{language}'.  "
            f"Available: {sorted(_REGISTRY.keys())}"
        )
    return _REGISTRY[language]


def register_parser(language: str, parser: BaseParser) -> None:
    """
    Dynamically register (or override) a parser at runtime.

    Example::

        from cast.parsers.registry import register_parser
        from my_project.parsers.rust_parser import RustParser

        register_parser("rust", RustParser())
    """
    _REGISTRY[language] = parser


def list_supported_languages() -> list[str]:
    """Return a sorted list of all languages with registered parsers."""
    return sorted(_REGISTRY.keys())