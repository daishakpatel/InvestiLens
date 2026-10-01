"""Company, financials, prices, filings, news, and latest-research endpoints (spec §24.2).

Route order matters: `/companies/search` is declared before `/companies/{ticker}` so the
literal path wins over the path parameter (fixes the v1 ambiguity).
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas.common import Freshness
from app.schemas.company import (
    Company,
    CompanyResponse,
    CompanySearchResult,
    FinancialsResponse,
    InsiderTransaction,
    MetricSeries,
    MetricSeriesPoint,
    OwnershipHolding,
    PricePoint,
    PricesResponse,
    ValuationResponse,
)
from app.schemas.filings import FilingSummary
from app.schemas.jobs import ResearchReportEnvelope
from app.schemas.news import NewsItem, NewsResponse
from app.schemas.research import ResearchReport
from app.schemas.sources import MetricResult

router = APIRouter(prefix="/companies", tags=["Company"])

_FRESH = Freshness(as_of="2026-09-29T00:00:00Z", source="sec", freshness_status="fresh")
_EXAMPLE_COMPANY = Company(
    ticker="NVDA",
    cik="0001045810",
    name="NVIDIA Corporation",
    exchange="NASDAQ",
    sector="Technology",
    industry="Semiconductors",
    fiscal_year_end="01-26",
)


# --- literal path FIRST (must precede /{ticker}) -------------------------------------
@router.get("/search", response_model=list[CompanySearchResult])
async def search_companies(q: str = Query(min_length=1)) -> list[CompanySearchResult]:
    """Fuzzy company search by name or ticker (FR-001)."""
    return [
        CompanySearchResult(
            ticker="NVDA", cik="0001045810", name="NVIDIA Corporation", exchange="NASDAQ", score=1.0
        )
    ]


@router.get("/{ticker}", response_model=CompanyResponse)
async def get_company(ticker: str) -> CompanyResponse:
    return CompanyResponse(company=_EXAMPLE_COMPANY, freshness=_FRESH)


@router.get("/{ticker}/financials", response_model=FinancialsResponse)
async def get_financials(
    ticker: str,
    metrics: str = Query(default="revenue,net_income"),
    period_type: str = Query(default="FY"),
    from_: int | None = Query(default=None, alias="from"),
    to: int | None = None,
) -> FinancialsResponse:
    series = [
        MetricSeries(
            metric_name=name,
            points=[
                MetricSeriesPoint(period="FY2025", period_end="2025-01-26", value=None, unit="USD")
            ],
        )
        for name in metrics.split(",")
    ]
    return FinancialsResponse(
        ticker=ticker.upper(), period_type=period_type, series=series, freshness=_FRESH
    )


@router.get("/{ticker}/metrics/{metric_name}/lineage", response_model=MetricResult)
async def get_metric_lineage(ticker: str, metric_name: str, period: str = "FY2025") -> MetricResult:
    """Show how a derived metric was computed (CIT-003)."""
    return MetricResult(value=None, unit="USD", inputs=[], formula_id=metric_name, warnings=[])


@router.get("/{ticker}/valuation", response_model=ValuationResponse)
async def get_valuation(ticker: str) -> ValuationResponse:
    return ValuationResponse(ticker=ticker.upper(), metrics=[], freshness=_FRESH)


@router.get("/{ticker}/prices", response_model=PricesResponse)
async def get_prices(
    ticker: str, start: str | None = None, end: str | None = None, interval: str = "1d"
) -> PricesResponse:
    return PricesResponse(
        ticker=ticker.upper(),
        interval=interval,
        points=[PricePoint(date="2026-09-29")],
        freshness=_FRESH,
    )


@router.get("/{ticker}/insiders", response_model=list[InsiderTransaction], tags=["Ownership"])
async def get_insiders(ticker: str) -> list[InsiderTransaction]:
    """Form 4 insider transactions (P2)."""
    return []


@router.get("/{ticker}/ownership", response_model=list[OwnershipHolding], tags=["Ownership"])
async def get_ownership(ticker: str) -> list[OwnershipHolding]:
    """13F institutional holdings (P2)."""
    return []


@router.get("/{ticker}/filings", response_model=list[FilingSummary], tags=["Filings"])
async def list_company_filings(
    ticker: str, type: str | None = None, limit: int = 50, cursor: str | None = None
) -> list[FilingSummary]:
    return [
        FilingSummary(
            filing_id="nvda_10k_2025",
            filing_type="10-K",
            filing_date="2025-02-26",
            period_end="2025-01-26",
            accession_number="0001045810-25-000023",
        )
    ]


@router.get("/{ticker}/news", response_model=NewsResponse, tags=["News"])
async def list_company_news(
    ticker: str,
    category: str | None = None,
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = None,
    source: str | None = None,
    min_relevance: float | None = None,
) -> NewsResponse:
    return NewsResponse(
        ticker=ticker.upper(),
        items=[NewsItem(news_id="news_9f2c1a", title="Example headline", publisher="seed")],
        freshness=Freshness(
            as_of="2026-09-29T00:00:00Z", source="finnhub", freshness_status="fresh"
        ),
    )


@router.get("/{ticker}/research/latest", response_model=ResearchReportEnvelope, tags=["Research"])
async def latest_research(ticker: str) -> ResearchReportEnvelope:
    return ResearchReportEnvelope(
        research_id="rpt_example",
        ticker=ticker.upper(),
        report=ResearchReport(
            executive_summary=[],
            company_overview=[],
            revenue_analysis=[],
            profitability_analysis=[],
            balance_sheet_analysis=[],
            cash_flow_analysis=[],
            valuation_analysis=[],
            news_summary=[],
            risks=[],
            management_commentary=[],
            bull_factors=[],
            bear_factors=[],
            insufficient_evidence_sections=[],
        ),
    )
