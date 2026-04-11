"""
cast.language_detector
~~~~~~~~~~~~~~~~~~~~~~
Maps a file path to a canonical language identifier using the file
extension.  The mapping is intentionally kept in a single dict so that
adding a new language is a one-liner.
"""

from __future__ import annotations

from pathlib import Path


# ---------------------------------------------------------------------------
# Extension → language identifier
# ---------------------------------------------------------------------------

EXTENSION_MAP: dict[str, str] = {
    # Python
    ".py":   "python",
    ".pyw":  "python",
    # JavaScript
    ".js":   "javascript",
    ".mjs":  "javascript",
    ".cjs":  "javascript",
    # TypeScript
    ".ts":   "typescript",
    ".tsx":  "typescript",
    # Java
    ".java": "java",
    # C
    ".c":    "c",
    ".h":    "c",
    # C++
    ".cpp":  "cpp",
    ".cc":   "cpp",
    ".cxx":  "cpp",
    ".hpp":  "cpp",
    ".hxx":  "cpp",
    # Go
    ".go":   "go",
    # Rust  (ready to plug a parser in later)
    ".rs":   "rust",
    # Ruby
    ".rb":   "ruby",
    # PHP
    ".php":  "php",
    # Swift
    ".swift":"swift",
    # Kotlin
    ".kt":   "kotlin",
    ".kts":  "kotlin",
}


class UnsupportedLanguageError(Exception):
    """Raised when no parser exists for the detected language."""


def detect_language(path: str | Path) -> str:
    """
    Return the canonical language string for *path*.

    Raises
    ------
    UnsupportedLanguageError
        If the extension is not in :data:`EXTENSION_MAP`.
    """
    suffix = Path(path).suffix.lower()
    if suffix not in EXTENSION_MAP:
        raise UnsupportedLanguageError(
            f"Unsupported file extension '{suffix}'.  "
            f"Supported extensions: {sorted(EXTENSION_MAP)}"
        )
    return EXTENSION_MAP[suffix]
