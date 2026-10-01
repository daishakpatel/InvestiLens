"""Parse 8-K item codes from a filing's own HTML (Phase 1a, scope item 5).

8-K item headers look like "Item 2.02", "Item 5.02". We extract the distinct codes in the
document. If the source already provides item codes (EDGAR `submissions.items`), the caller may
prefer those; this is the fallback that works on raw bytes too.
"""

from __future__ import annotations

import html
import re

_TAG_RE = re.compile(r"<[^>]+>")
_ITEM_RE = re.compile(r"Item\s+(\d\.\d{2})")


def parse_8k_items(document: bytes) -> list[str]:
    text = html.unescape(_TAG_RE.sub(" ", document.decode("utf-8", errors="ignore")))
    return sorted({m.group(1) for m in _ITEM_RE.finditer(text)})
