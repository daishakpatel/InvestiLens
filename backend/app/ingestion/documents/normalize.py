"""Text normalization for parsed filing text (DP-003)."""

from __future__ import annotations

import re
import unicodedata

_WS = re.compile("[ \t\xa0]+")
_BLANKLINES = re.compile(r"\n{3,}")
_DEHYPHEN = re.compile(r"(\w)-\n(\w)")  # word broken across a line by a hyphen
_PAGE_NUMBER_LINE = re.compile(r"(?m)^\s*\d{1,4}\s*$")  # lone page numbers (headers/footers)


def normalize_text(text: str) -> str:
    """Unicode-normalize, de-hyphenate line breaks, drop lone page numbers, tidy whitespace."""
    text = unicodedata.normalize("NFKC", text)
    text = _DEHYPHEN.sub(r"\1\2", text)
    text = _PAGE_NUMBER_LINE.sub("", text)
    text = _WS.sub(" ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    text = _BLANKLINES.sub("\n\n", text)
    return text.strip()
