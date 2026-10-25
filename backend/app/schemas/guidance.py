"""Guidance vs actual responses (Phase 7i, FR-GD-014). Money is raw USD, ratios are decimals."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

Result = Literal[
    "above_range", "within_range", "below_range", "not_comparable", "actual_unavailable"
]


class GuidanceOutcomeView(BaseModel):
    result: Result
    actual_value: Decimal | None  # null with a reason, never zero
    actual_source_ids: list[str]  # financial_metrics source IDs; a ratio cites both inputs
    delta_vs_low: Decimal | None
    delta_vs_high: Decimal | None
    delta_vs_mid: Decimal | None  # money in USD, ratios in ratio points
    delta_vs_mid_pct: Decimal | None  # delta over the midpoint, as a decimal
    reason_code: str | None
    explanation: str | None  # why it is not compared, in words
    computed_at: datetime


class GuidanceRelease(BaseModel):
    document_id: int
    title: str | None
    url: str | None


class GuidanceValue(BaseModel):
    """One guided figure as one release stated it."""

    id: int
    issued_at: datetime | None
    low: Decimal | None  # a range (`derived_range` when computed from "plus or minus")
    high: Decimal | None
    point: Decimal | None  # or a single figure
    midpoint: Decimal
    derived_range: bool
    quote: str  # the release's own words
    source_id: str  # the paragraph's backend source ID; opens the citation drawer
    release: GuidanceRelease
    outcome: GuidanceOutcomeView | None


class GuidanceRow(GuidanceValue):
    """The initial guidance for a period, metric and basis (the headline), with later revisions."""

    fiscal_year: int
    fiscal_period: str  # Q1..Q4 | FY
    period_label: str  # "Q3 FY2027"
    metric: str
    metric_label: str
    basis: Literal["gaap", "non_gaap", "unspecified"]
    unit: Literal["usd", "ratio", "percent_of_revenue"]
    revisions: list[GuidanceValue]


class GuidanceResponse(BaseModel):
    ticker: str
    fiscal_year: int | None
    fiscal_years: list[int]  # years with verified guidance, newest first
    items: list[GuidanceRow]
    scope: str  # company guidance only; no consensus estimates


class TrackRecordQuarter(BaseModel):
    period_label: str
    low: Decimal
    high: Decimal
    actual_value: Decimal | None
    result: Result
    delta_vs_mid_pct: Decimal | None
    source_id: str


class GuidanceTrackRecord(BaseModel):
    ticker: str
    metric: str
    metric_label: str
    n_quarters: int
    n_comparable: int
    n_above: int
    n_within: int
    n_below: int
    avg_delta_vs_mid: Decimal | None
    avg_delta_vs_mid_pct: Decimal | None
    sufficient: bool  # shown only from 4 comparable quarters
    label: str  # positional wording, or "Insufficient history (n=3)"
    quarters: list[TrackRecordQuarter]  # newest first, for the range-vs-actual plot
