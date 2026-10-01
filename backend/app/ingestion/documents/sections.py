"""Section detection for SEC filings (DP-001).

Detects Item headings (10-K) / Part+Item (10-Q), de-duplicates the table-of-contents copy of each
heading (the real heading is the later occurrence), assigns every block to a section, and reports
a confidence score so low-confidence parses can be flagged rather than trusted silently.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.ingestion.documents.blocks import Block

# A heading block starts with "Item N[letter]" and is short (not a sentence referencing an item).
_ITEM_RE = re.compile(r"^item\s+(\d+[a-z]?)\b[.:)\s-]*(.*)$", re.I)
_MAX_HEADING_CHARS = 200

# Core 10-K items used to score detection confidence.
_CORE_10K = {"1", "1A", "2", "3", "5", "7", "7A", "8", "9A"}


@dataclass
class Section:
    item_code: str  # e.g. "1A", "7"
    title: str
    section_path: list[str]
    start_idx: int  # index into the blocks list (the heading block)
    end_idx: int  # exclusive


@dataclass
class SectionResult:
    sections: list[Section]
    confidence: float  # 0-1; fraction of core items detected
    low_confidence: bool


def _heading_candidate(block: Block) -> tuple[str, str] | None:
    if block.kind != "text" or len(block.text) > _MAX_HEADING_CHARS:
        return None
    match = _ITEM_RE.match(block.text.strip())
    if not match:
        return None
    return match.group(1).upper(), match.group(2).strip()


def detect_sections(blocks: list[Block], filing_type: str) -> SectionResult:
    """Return the detected sections (TOC-deduplicated) with a confidence score."""
    # Collect every heading candidate, then keep the LAST occurrence of each item code
    # (the first is the table of contents).
    last_by_code: dict[str, tuple[int, str]] = {}
    for idx, block in enumerate(blocks):
        candidate = _heading_candidate(block)
        if candidate is not None:
            code, title = candidate
            last_by_code[code] = (idx, title)

    starts = sorted(((idx, code, title) for code, (idx, title) in last_by_code.items()))
    sections: list[Section] = []
    for position, (idx, code, title) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(blocks)
        label = f"Item {code}"
        full_title = f"{label}. {title}".strip(". ") if title else label
        sections.append(Section(code, full_title, [label], idx, end))

    detected_core = {s.item_code for s in sections} & _CORE_10K
    confidence = (
        len(detected_core) / len(_CORE_10K)
        if filing_type.startswith("10-K")
        else (1.0 if sections else 0.0)
    )
    return SectionResult(sections=sections, confidence=confidence, low_confidence=confidence < 0.8)
