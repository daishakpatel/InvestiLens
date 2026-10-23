"""Filing list, detail, and section schemas (spec §24.2)."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class FilingSummary(BaseModel):
    filing_id: str
    filing_type: str
    filing_date: str | None = None
    period_end: str | None = None
    accession_number: str
    primary_document_url: str | None = None
    # "filing" or "late_filing_notice" (NT 10-K / NT 10-Q), FR-EX-009. None when not looked up.
    document_type: str | None = None


class FilingDetail(FilingSummary):
    company_ticker: str
    items: list[str] | None = None
    source_url: str | None = None


class FilingSection(BaseModel):
    section_path: list[str]
    title: str
    char_start: int | None = None
    char_end: int | None = None


class FilingSectionsResponse(BaseModel):
    filing_id: str
    sections: list[FilingSection]


# --- Filing diff (§37.4, Phase 6b) ---

ChangeStatus = Literal["unchanged", "reworded", "new", "removed"]


class DiffPassage(BaseModel):
    """One side of a diff item. `source_ids` are backend-issued and resolve via /sources/{id}."""

    heading: str
    source_ids: list[str]
    text: str | None = None  # only for new/removed; a reworded passage is carried by `word_diff`


class DiffOp(BaseModel):
    op: Literal["equal", "insert", "delete"]
    text: str


class FilingDiffItem(BaseModel):
    section: str
    kind: Literal["risk_factor", "section"]
    status: ChangeStatus
    # heading | similarity = deterministic; llm = adjudicated borderline pair; threshold = a
    # borderline pair decided by the fallback threshold because no adjudication was available.
    decided_by: Literal["heading", "similarity", "llm", "threshold"]
    similarity: float | None = None
    old: DiffPassage | None = None
    new: DiffPassage | None = None
    word_diff: list[DiffOp] | None = None


class FilingDiffCounts(BaseModel):
    unchanged: int = 0
    reworded: int = 0
    new: int = 0
    removed: int = 0


class FilingDiffResponse(BaseModel):
    company_ticker: str
    filing: FilingSummary
    against: FilingSummary
    similarity_method: Literal["lexical", "embedding"]
    # "heuristic" = raw filing styling was unavailable, so risk captions were guessed (less precise)
    caption_detection: Literal["emphasis", "heuristic"]
    counts: FilingDiffCounts  # over `items`
    items: list[FilingDiffItem]


# --- Earnings-day price reaction (§37.3) ---


class EarningsReaction(BaseModel):
    filing: FilingSummary
    pre_date: str | None = None
    pre_close: Decimal | None = None  # adjusted close, USD
    post_date: str | None = None
    post_close: Decimal | None = None
    move: Decimal | None = None  # ratio (0.05 = +5%); None => see `reason`
    reason: str | None = None


class EarningsResponse(BaseModel):
    ticker: str
    method: str
    events: list[EarningsReaction]


# --- Management language tracking (§37.5) ---


class LanguageStatement(BaseModel):
    source_id: str
    text: str
    mentions: int


class LanguagePoint(BaseModel):
    filing_id: str
    count: int
    per_1k_words: float
    flag: Literal["first_appearance", "disappeared"] | None = None
    statements: list[LanguageStatement]


class LanguagePeriod(BaseModel):
    filing_id: str
    filing_type: str
    filing_date: str | None = None
    period_end: str | None = None
    word_count: int


class LanguageSeries(BaseModel):
    topic: str
    label: str
    points: list[LanguagePoint]  # one per period, same order as `periods`


class ManagementLanguageResponse(BaseModel):
    ticker: str
    taxonomy_version: str
    hedging_lexicon_version: str
    # Lexicon counts over MD&A text. A signal about wording, not an AI judgment or a sentiment.
    method: str
    periods: list[LanguagePeriod]  # oldest first
    topics: list[LanguageSeries]
    hedging: LanguageSeries
