"""8-K item codes as full dotted codes (Phase 7c, FR-EX-001/002, ADR-0041).

An 8-K's items are "Item 5.02", "Item 2.02", … The 10-K/10-Q heading parser collapsed these to
"5" and "2", so a CFO departure (5.02) and a shareholder vote (5.07) looked the same. This module
keeps the whole code and tolerates real-world formatting: a trailing period ("Item 5.02."),
upper case, non-breaking spaces, and en/em dashes or a colon before the title.
"""

from __future__ import annotations

import html
import re
import unicodedata

# "Item 5.02" / "ITEM 5.02." / "Item 5.02 <en or em dash> Departure of …" / "Item 5.02: …" (after
# NFKC, which turns a non-breaking space into a plain one).
_HEADING = re.compile(
    r"^item\s+(?P<major>\d{1,2})\s*\.\s*(?P<minor>\d{2})(?!\d)\.?\s*(?:[-\u2013\u2014:]\s*)?(?P<title>.*)$",
    re.I,
)
_MENTION = re.compile(r"\bitem\s+(\d{1,2})\s*\.\s*(\d{2})(?!\d)", re.I)
_TAG = re.compile(r"<[^>]+>")
_MAX_HEADING_CHARS = 200  # a heading, not a sentence that mentions an item


def _normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).split())


def parse_item_heading(text: str) -> tuple[str, str] | None:
    """(code, title) when `text` is an 8-K item heading, e.g. ("5.02", "Departure of …")."""
    clean = _normalize(text)
    if len(clean) > _MAX_HEADING_CHARS:
        return None
    match = _HEADING.match(clean)
    if match is None:
        return None
    code = f"{int(match['major'])}.{match['minor']}"
    return code, match["title"].strip().rstrip(".").strip()


def item_codes_in_document(document: bytes) -> list[str]:
    """Every distinct dotted item code mentioned in raw 8-K HTML, sorted.

    The fallback item list when the filing index gives none (FR-EX-003): raw bytes, any case,
    non-breaking spaces.
    """
    text = _normalize(html.unescape(_TAG.sub(" ", document.decode("utf-8", errors="ignore"))))
    return sorted({f"{int(m[1])}.{m[2]}" for m in _MENTION.finditer(text)}, key=_order)


def _order(code: str) -> tuple[int, int]:
    major, minor = code.split(".")
    return int(major), int(minor)
