"""Company, financials, prices, and ownership response schemas (spec §24.2)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import Freshness
from app.schemas.sources import MetricResult


class Company(BaseModel):
    ticker: str
    cik: str
    name: str
    exchange: str | None = None
    sector: str | None = None
    industry: str | None = None
    fiscal_year_end: str | None = None


class CompanySearchResult(BaseModel):
    """A single fuzzy-search hit (FR-001)."""

    ticker: str
    cik: str
    name: str
    exchange: str | None = None
    score: float = Field(ge=0, le=1)


class CompanyResponse(BaseModel):
    company: Company
    freshness: Freshness


class MetricSeriesPoint(BaseModel):
    period: str  # e.g. "FY2025" (fiscal, kept separate from calendar dates)
    period_end: str | None = None  # ISO-8601 calendar date
    value: Decimal | None
    unit: str


class MetricSeries(BaseModel):
    metric_name: str
    points: list[MetricSeriesPoint]


class FinancialsResponse(BaseModel):
    ticker: str
    period_type: str  # FY|Q|TTM
    series: list[MetricSeries]
    freshness: Freshness


class ValuationResponse(BaseModel):
    ticker: str
    metrics: list[MetricResult]
    freshness: Freshness


class PricePoint(BaseModel):
    date: str  # ISO-8601 date
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    close: Decimal | None = None
    adj_close: Decimal | None = None
    volume: int | None = None


class PricesResponse(BaseModel):
    ticker: str
    unit: str = "USD"
    interval: str = "1d"
    points: list[PricePoint]
    freshness: Freshness


class InsiderTransaction(BaseModel):
    insider_name: str
    role: str | None = None
    transaction_date: str | None = None
    code: str | None = None
    shares: int | None = None
    price: Decimal | None = None


class OwnershipHolding(BaseModel):
    filer_name: str
    period_end: str | None = None
    shares: int | None = None
    value: Decimal | None = None
    change_shares: int | None = None
