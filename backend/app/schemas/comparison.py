"""Company-comparison API contracts (Phase 6a, §37.1).

Side-by-side metrics are calendarized (aligned fiscal periods) and sector-normalized (percentile vs
the peer set). Every number is a `MetricResult` (DR-040) — NULL + reason code, never a fake zero.
AI commentary, when present, is a Phase 3a `VerifiedOutput`: cited, verified, non-advisory.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.citations import VerifiedOutput
from app.schemas.sources import MetricResult

# §37.1 compare set: revenue (scale), growth, margins, FCF, debt, P/E, profitability. Names map to
# persisted `financial_metrics.metric_name`; price-dependent ones (pe_ratio) surface N/A until the
# Phase 1d price-metric wiring lands — honest, not faked.
DEFAULT_COMPARISON_METRICS: tuple[str, ...] = (
    "revenue",
    "yoy_growth",
    "gross_margin",
    "operating_margin",
    "net_margin",
    "free_cash_flow",
    "fcf_margin",
    "total_debt",
    "debt_to_equity",
    "pe_ratio",
    "roe",
)


class ComparisonCommentaryRequest(BaseModel):
    """Request for AI comparison commentary (POST — gated by auth + AI budget, like research)."""

    tickers: list[str] = Field(min_length=2, max_length=6)
    metrics: list[str] | None = None
    period: str | None = None


class PeerSuggestion(BaseModel):
    """A suggested comparable company (§37.1 peer set by SIC/industry + market-cap band)."""

    ticker: str
    name: str
    sic_code: str | None = None
    sector: str | None = None
    industry: str | None = None
    market_cap: MetricResult | None = None  # None when price-dependent metrics are unavailable
    reason: str  # why it was suggested, e.g. "same SIC 3674; market cap within band"


class PeerSuggestionsResponse(BaseModel):
    target: str
    peers: list[PeerSuggestion] = []
    notes: list[str] = []  # degradations (e.g. "market-cap band unavailable")


class ComparisonCompany(BaseModel):
    """One company's alignment info in the comparison (calendarization transparency, DR-021)."""

    ticker: str
    name: str
    sic_code: str | None = None
    sector: str | None = None
    fiscal_year_end: str | None = None
    fiscal_period: str | None = None  # the actual period used, e.g. NVDA "FY2025" vs AMD "FY2024"
    calendar_year: int | None = None
    period_end: str | None = None  # ISO date of the period actually used


class ComparisonCell(BaseModel):
    """One company's value for one metric, with its sector-normalized percentile vs the peer set."""

    ticker: str
    result: MetricResult
    percentile: Decimal | None = (
        None  # fraction of peers at-or-below this value (DR reuses 1c util)
    )


class ComparisonMetricRow(BaseModel):
    metric_name: str
    unit: str
    cells: list[ComparisonCell] = []


class ComparisonResponse(BaseModel):
    calendar_year: int | None = None
    companies: list[ComparisonCompany] = []
    metrics: list[ComparisonMetricRow] = []
    commentary: VerifiedOutput | None = None  # cited, verified differences only (§37.1)
    notes: list[str] = []
    disclaimer: str = Field(
        default="Analysis only — not investment advice or a buy/sell/hold recommendation."
    )
