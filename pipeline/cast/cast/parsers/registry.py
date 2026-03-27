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

from cast.parsers.base_parser import BaseParser
from cast.parsers.python_parser import PythonParser

logger = logging.getLogger(__name__)

def _get_parser_with_fallback(language: str) -> BaseParser:
    """
    Attempt to initialize the robust TreeSitterParser. If the proper C-compiler
    toolchains or language bindings are missing in the environment, fallback to
    the heuristic BraceLanguageParser.
    """
    try:
        from cast.parsers.tree_sitter_parser import TreeSitterParser
        return TreeSitterParser(language)
    except (ImportError, ValueError) as e:
        logger.debug(f"TreeSitterParser unavailable for {language}: {e}. Falling back.")
        from cast.parsers.brace_language_parser import BraceLanguageParser
        return BraceLanguageParser(language)

# ---------------------------------------------------------------------------
# Registry  ─  language_id → parser instance
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, BaseParser] = {
    "python":     PythonParser(),
    "javascript": _get_parser_with_fallback("javascript"),
    "typescript": _get_parser_with_fallback("typescript"),
    "java":       _get_parser_with_fallback("java"),
    "c":          _get_parser_with_fallback("c"),
    "cpp":        _get_parser_with_fallback("cpp"),
    "go":         _get_parser_with_fallback("go"),
    "rust":       _get_parser_with_fallback("rust"),
    "ruby":       _get_parser_with_fallback("ruby"),
    "php":        _get_parser_with_fallback("php"),
}

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
