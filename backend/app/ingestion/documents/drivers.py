"""MD&A 'driver' language detection (CH-007).

Flags paragraphs explaining *why* a number moved ('the increase was primarily due to …'), so
causal-explanation questions can boost them later. Lexicon-based and deterministic.
"""

from __future__ import annotations

import re

_DRIVER_PATTERNS = re.compile(
    r"(?i)(primarily due to|driven by|attributable to|as a result of|"
    r"reflecting|partially offset by|increase was|decrease was|"
    r"was primarily|resulted from|owing to)"
)


def is_driver_language(text: str) -> bool:
    return bool(_DRIVER_PATTERNS.search(text))
