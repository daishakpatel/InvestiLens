"""Earnings calendar, pre-earnings preview and post-earnings brief (Phase 7j, §37.3, ADR-0048).

Every figure here is read from stored data with the source IDs the rest of the app cites; the
only model-written text is a watch item's one-sentence rewording and the brief's short narrative,
both checked in code. A section whose inputs are missing is listed in `missing` with a plain
reason instead of being filled.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.guidance import GuidanceRow, GuidanceTrackRecord
from app.schemas.red_flags import RedFlagItem

Kind = Literal["preview", "brief"]
DateSource = Literal["sec_8k", "announcement", "estimated"]
EventStatus = Literal["scheduled", "reported", "unknown"]
ReportTime = Literal["bmo", "amc", "unknown"]


class CalendarEvent(BaseModel):
    fiscal_year: int
    fiscal_period: str  # Q1..Q4
    period_label: str  # "Q3 FY2027"
    report_date: date | None
    report_time: ReportTime
    source: DateSource
    status: EventStatus
    estimated: bool  # shown as "~" and never notifies on its own (FR-EB-002)
    source_id: str | None = None  # filing:<id> for a reported date, a paragraph ID if announced
    quote: str | None = None  # the announcement's own words


class EarningsCalendarResponse(BaseModel):
    ticker: str
    upcoming: CalendarEvent | None
    events: list[CalendarEvent]  # newest first
    method: str


class Missing(BaseModel):
    """A section left out because an input is missing: shown as "Not available: {reason}"."""

    section: str
    reason: str


class MetricRow(BaseModel):
    """One reported figure against the prior quarter and the prior-year quarter. `change_*` is
    growth (a ratio) for money and per-share figures, a difference in ratio points for margins."""

    metric: str
    label: str
    unit: Literal["usd", "usd_per_share", "ratio"]
    change_kind: Literal["growth", "points"]
    value: Decimal | None
    source_ids: list[str] = []
    prior_quarter: Decimal | None = None
    prior_quarter_source_ids: list[str] = []
    change_vs_prior_quarter: Decimal | None = None
    prior_year: Decimal | None = None
    prior_year_source_ids: list[str] = []
    change_vs_prior_year: Decimal | None = None
    reason: str | None = None  # why `value` is None


class MetricTable(BaseModel):
    fiscal_year: int
    fiscal_period: str
    period_label: str
    prior_quarter_label: str
    prior_year_label: str
    rows: list[MetricRow]


class ValuationLine(BaseModel):
    multiple: str  # pe_ratio | ev_ebitda
    label: str
    value: Decimal
    source_ids: list[str]
    own_label: str | None = None  # positional only (FR-PS-011)
    own_n: int = 0
    peer_label: str | None = None
    peer_n: int = 0


class ValuationSnapshot(BaseModel):
    as_of: date | None
    lines: list[ValuationLine]


class Reaction(BaseModel):
    """The price move around the earnings 8-K, described, never interpreted."""

    filing_id: int
    filing_date: date | None
    pre_date: date | None = None
    post_date: date | None = None
    move_at_open: Decimal | None = None
    move: Decimal | None = None  # first session's close vs the prior close
    move_5d: Decimal | None = None
    volume_ratio: Decimal | None = None
    source_ids: list[str] = []
    reason: str | None = None


class WatchItem(BaseModel):
    kind: Literal["growth_deceleration", "new_risk_factor", "topic_rise", "margin_reversal"]
    text: str
    source_ids: list[str] = Field(min_length=1)
    reworded: bool = False  # True when the model's one-sentence rewording passed the checks


class ChangedPassage(BaseModel):
    status: Literal["new", "removed", "reworded"]
    heading: str
    old_quote: str | None = None
    new_quote: str | None = None
    source_ids: list[str]


class TopicShift(BaseModel):
    topic: str
    label: str
    before_per_1k: float  # lexicon mentions per 1,000 MD&A words (topic_taxonomy_v1)
    after_per_1k: float
    source_ids: list[str]


class WhatChanged(BaseModel):
    filing_id: int
    filing_type: str
    filing_date: date | None
    against_filing_id: int
    against_filing_date: date | None
    new_risks: int
    removed_risks: int
    reworded_risks: int
    top_changes: list[ChangedPassage]
    topic_shifts: list[TopicShift]


class NarrativeSentence(BaseModel):
    text: str
    source_ids: list[str] = Field(min_length=1)


class Narrative(BaseModel):
    sentences: list[NarrativeSentence]  # at most 4, at most 120 words in all (FR-EB-006)
    dropped: int  # proposed sentences that failed verification and were left out
    prompt_version: str
    model: str


class BriefHeader(BaseModel):
    ticker: str
    company_name: str | None
    fiscal_year: int
    fiscal_period: str
    period_label: str
    report_date: date | None
    report_time: ReportTime
    date_source: DateSource
    date_estimated: bool
    date_source_id: str | None = None


class EarningsPreview(BaseModel):
    """What to watch before a report (FR-EB-004/005). Never what will happen."""

    header: BriefHeader
    last_quarter_snapshot: MetricTable | None = None
    guidance_for_period: list[GuidanceRow] = []
    track_record: GuidanceTrackRecord | None = None
    valuation_snapshot: ValuationSnapshot | None = None
    open_flags: list[RedFlagItem] = []
    last_reaction: Reaction | None = None
    watch_items: list[WatchItem] = []
    missing: list[Missing] = []


class EarningsBrief(BaseModel):
    """What was reported and what changed, after a report (FR-EB-006)."""

    header: BriefHeader
    headline_table: MetricTable | None = None
    versus_guidance: list[GuidanceRow] = []
    reaction: Reaction | None = None
    what_changed: WhatChanged | None = None
    new_flags: list[RedFlagItem] = []
    narrative: Narrative | None = None
    missing: list[Missing] = []


class StoredBrief(BaseModel):
    id: int
    kind: Kind
    fiscal_year: int
    fiscal_period: str
    period_label: str
    version: int
    inputs_label: str  # what changed from the previous version ("after 10-Q filed")
    created_at: datetime
    preview: EarningsPreview | None = None  # set when kind == "preview"
    brief: EarningsBrief | None = None  # set when kind == "brief"


class EarningsBriefsResponse(BaseModel):
    ticker: str
    items: list[StoredBrief]  # newest first: latest period, then highest version
    scope: str


class GenerateBriefRequest(BaseModel):
    kind: Kind


class GenerateBriefResponse(BaseModel):
    created: bool  # False: the inputs were unchanged and the stored version was returned
    item: StoredBrief
