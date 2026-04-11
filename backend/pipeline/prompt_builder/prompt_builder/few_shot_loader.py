"""
prompt_builder.few_shot_loader
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Loads ``few_shot_examples.json`` and provides efficient lookup by
(language, chunk_type) pair.

Designed so that the few-shot file is entirely optional — if it is
missing or empty, every lookup simply returns ``None`` and the pipeline
continues without injecting examples.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class FewShotLoader:
    """
    Reads the few-shot examples JSON file and indexes entries by
    ``(language, chunk_type)``.

    If multiple examples exist for the same pair the first one wins.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self._index: dict[tuple[str, str], dict] = {}

        if path is None:
            path = Path(__file__).parent / "few_shot_examples.json"

        if not path.exists():
            logger.warning("few_shot_examples.json not found at %s — skipping", path)
            return

        try:
            with path.open(encoding="utf-8") as fh:
                data = json.load(fh)
            examples = data.get("examples", [])
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not load few-shot examples: %s", exc)
            return

        for ex in examples:
            key = (ex.get("language", "").lower(), ex.get("chunk_type", "").lower())
            # First entry per key wins — ordering in the JSON file is intentional
            if key not in self._index:
                self._index[key] = ex

    def get(self, language: str, chunk_type: str) -> Optional[dict]:
        """
        Return the example dict for *(language, chunk_type)*, or ``None``.

        Falls back through:
          1. (language, chunk_type)  — exact match
          2. ("*",       chunk_type) — type wildcard
          3. (language,  "*")        — language wildcard
        """
        lang  = language.lower()
        ctype = chunk_type.lower()

        return (
            self._index.get((lang, ctype))
            or self._index.get(("*", ctype))
            or self._index.get((lang, "*"))
        )

    @property
    def count(self) -> int:
        return len(self._index)
