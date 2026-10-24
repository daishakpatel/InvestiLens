"""Footnote responses (Phase 7f, FR-FN-008..011)."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.schemas.filings import FilingSummary

SummaryStatus = Literal["summarised", "abstained", "pending"]


class NoteBullet(BaseModel):
    """One AI bullet. `quote` is verbatim from the paragraph `paragraph_id` (a source ID)."""

    text: str
    quote: str
    paragraph_id: str


class NoteSummary(BaseModel):
    """`note_summary_v1` output after verification: bullets that failed are dropped, and a summary
    with none left abstains (FR-FN-007)."""

    note_id: str
    bullets: list[NoteBullet]
    abstain: bool
    dropped: int = 0  # bullets the model returned that failed verification
    prompt_version: str
    model: str


class NoteSummaryView(BaseModel):
    """`pending` = not generated yet (summaries are made after parsing, never on page load)."""

    status: SummaryStatus
    bullets: list[NoteBullet] = []
    model: str | None = None


class NoteItem(BaseModel):
    note_id: str
    number: int
    title: str
    category: str  # note_taxonomy_v1
    also_matches: list[str] = []  # other categories the title matched (priority tie)
    paragraph_ids: list[str]  # the note's chunks: each opens in the citation drawer
    summary: NoteSummaryView | None = None  # only for summarised categories


class NotesResponse(BaseModel):
    company_ticker: str
    filing: FilingSummary
    taxonomy: str
    low_confidence: bool  # fewer notes than a 10-K should have: segmentation may be wrong
    summarised_categories: list[str]
    notes: list[NoteItem]


class FootnoteFact(BaseModel):
    metric: str
    label: str  # "Lease-adjusted debt": the adjustment is always named
    value: Decimal | None
    unit: str  # USD, ratio (0.0438 = 4.38%), years
    period: str  # FY2026
    source_id: str  # xbrl:… or derived:…, resolvable via /sources/{id}
    is_derived: bool
    formula: str | None = None  # for derived figures
    from_inline_xbrl: bool = False  # read from the 10-K's inline XBRL, not companyfacts


class FootnoteGap(BaseModel):
    metric: str
    label: str
    period: str
    reason: str  # not_tagged | filing_unavailable | MISSING_INPUT


class FootnoteCategory(BaseModel):
    category: str
    facts: list[FootnoteFact]
    gaps: list[FootnoteGap]


class FootnoteFactsResponse(BaseModel):
    company_ticker: str
    fiscal_year: int | None  # the latest fiscal year with footnote facts; null if none yet
    categories: list[FootnoteCategory]
