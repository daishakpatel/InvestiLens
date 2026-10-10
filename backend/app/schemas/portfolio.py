"""Portfolio-analysis API contracts (Phase 6a, §37.2).

Analysis over user-entered *hypothetical* weights — never a recommendation (LGL-006), never live
positions or brokerage data (out of scope, §4.2). Every number is deterministic backend math; the
response also carries the per-holding data the frontend needs to recompute weighted metrics,
concentration, and portfolio volatility on a what-if weight change without a backend round-trip.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.sources import MetricResult


class Holding(BaseModel):
    ticker: str
    weight: Decimal = Field(gt=0)  # as entered; normalized to sum to 1 in the response


class PortfolioRequest(BaseModel):
    holdings: list[Holding] = Field(min_length=1)
    metrics: list[str] | None = None  # defaults to the standard weighted set


class NormalizedHolding(BaseModel):
    ticker: str
    name: str
    weight: Decimal  # normalized to sum to 1
    sector: str | None = None


class WeightedMetric(BaseModel):
    """A portfolio-weighted metric. `coverage` is the fraction of weight that had a value (weights
    are renormalized over covered holdings); value is NULL when coverage is 0 (DR-041 spirit)."""

    metric_name: str
    unit: str
    value: Decimal | None
    coverage: Decimal
    warnings: list[str] = []


class SectorExposure(BaseModel):
    sector: str
    weight: Decimal


class Concentration(BaseModel):
    """Herfindahl-Hirschman Index of holding weights (sum of squares, decimal). 1 = one holding."""

    hhi: Decimal
    effective_holdings: Decimal  # 1 / HHI
    top_holding: str | None = None
    top_weight: Decimal | None = None


class HoldingContribution(BaseModel):
    ticker: str
    description: str
    source_ids: list[str] = []


class RiskTheme(BaseModel):
    """A risk category shared across holdings; each contribution is cited back to its filing."""

    category: str
    holding_count: int
    portfolio_weight: Decimal  # summed weight of holdings exposed to this theme
    contributions: list[HoldingContribution] = []


class CorrelationRow(BaseModel):
    ticker: str
    correlations: dict[str, Decimal]  # other ticker -> Pearson correlation of daily returns


class HoldingVolatility(BaseModel):
    ticker: str
    annualized_volatility: Decimal | None = None  # None when price history is unavailable
    observations: int = 0


class RiskStats(BaseModel):
    """Deterministic price-based risk, computed from `price_history` daily returns."""

    window_start: str | None = None
    window_end: str | None = None
    holding_volatility: list[HoldingVolatility] = []
    correlation: list[CorrelationRow] = []
    portfolio_volatility: Decimal | None = None
    notes: list[str] = []


class HoldingData(BaseModel):
    """Per-holding raw inputs so the client can recompute aggregates on a what-if weight change."""

    ticker: str
    sector: str | None = None
    metrics: dict[str, MetricResult] = {}
    annualized_volatility: Decimal | None = None


class PortfolioAnalysis(BaseModel):
    holdings: list[NormalizedHolding] = []
    weighted_metrics: list[WeightedMetric] = []
    sector_exposure: list[SectorExposure] = []
    concentration: Concentration | None = None
    risk_stats: RiskStats | None = None
    risk_themes: list[RiskTheme] = []
    holdings_data: list[HoldingData] = []  # inputs for client-side what-if recompute
    notes: list[str] = []
    disclaimer: str = Field(
        default=(
            "Analysis of a hypothetical portfolio for informational purposes only — not investment "
            "advice and not a recommendation to buy, sell, hold, or rebalance any security."
        )
    )
