"""Company, financials, prices, filings, news, and latest-research endpoints (spec §24.2).

Thin HTTP layer over the repositories: resolve the company, read its data, attach freshness
(API-008), and paginate list endpoints by opaque cursor (API-002). Route order matters:
`/companies/search` is declared before `/companies/{ticker}` so the literal path wins.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api._support import freshness_for, metric_to_result
from app.api.filings import to_summary
from app.api.pagination import NEXT_CURSOR_HEADER, clamp_limit, decode_cursor, encode_cursor
from app.cache import cache
from app.db import get_db
from app.filings import topics
from app.filings.earnings import earnings_reactions
from app.ingestion.documents.chunker import PARSER_VERSION
from app.models import Company as CompanyModel
from app.models import DocumentChunk
from app.repositories import companies as company_repo
from app.repositories import filings as filing_repo
from app.repositories import metrics as metric_repo
from app.repositories import news as news_repo
from app.repositories import prices as price_repo
from app.repositories import reports as report_repo
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
from app.schemas.filings import (
    EarningsReaction,
    EarningsResponse,
    FilingSummary,
    LanguagePeriod,
    LanguagePoint,
    LanguageSeries,
    LanguageStatement,
    ManagementLanguageResponse,
)
from app.schemas.jobs import ResearchReportEnvelope
from app.schemas.news import NewsItem, NewsResponse
from app.schemas.research import ResearchReport
from app.schemas.sources import MetricResult

router = APIRouter(prefix="/companies", tags=["Company"])

_DB = Depends(get_db)

# Price-dependent valuation metrics (§12). Persisted once Phase 1d price-metric wiring lands; until
# then this returns whichever of them exist, and an empty list otherwise (documented, not faked).
_VALUATION_METRICS = [
    "market_cap",
    "enterprise_value",
    "pe_ratio",
    "ps_ratio",
    "ev_revenue",
    "ev_ebitda",
    "fcf_yield",
]


def _resolve(db: Session, ticker: str) -> CompanyModel:
    company = company_repo.get_by_ticker(db, ticker)
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"company {ticker.upper()} not ingested")
    return company


def _parse_date(value: str | None, field: str) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"invalid {field} date") from exc


def _parse_dt(value: str | None, field: str) -> datetime | None:
    d = _parse_date(value, field)
    return datetime(d.year, d.month, d.day, tzinfo=UTC) if d else None


def _to_company(row: CompanyModel) -> Company:
    return Company(
        ticker=row.ticker,
        cik=row.cik,
        name=row.name,
        exchange=row.exchange,
        sector=row.sector,
        industry=row.industry,
        fiscal_year_end=row.fiscal_year_end,
    )


# --- literal path FIRST (must precede /{ticker}) -------------------------------------
@router.get("/search", response_model=list[CompanySearchResult])
async def search_companies(
    q: str = Query(min_length=1), limit: int | None = None, db: Session = _DB
) -> list[CompanySearchResult]:
    """Fuzzy company search by name or ticker (FR-001)."""
    rows = company_repo.search(db, q, limit=clamp_limit(limit))
    needle = q.strip().upper()
    out: list[CompanySearchResult] = []
    for row in rows:
        if row.ticker.upper() == needle:
            score = 1.0
        elif row.ticker.upper().startswith(needle):
            score = 0.8
        else:
            score = 0.5
        out.append(
            CompanySearchResult(
                ticker=row.ticker, cik=row.cik, name=row.name, exchange=row.exchange, score=score
            )
        )
    return out


@router.get("/{ticker}", response_model=CompanyResponse)
async def get_company(ticker: str, db: Session = _DB) -> CompanyResponse:
    """Company profile (spec §25.3's cache example). Read-through Redis cache when enabled; the
    loader is the DB read, so a cache miss or outage is transparent (CACHE-005)."""

    def _load() -> dict[str, object]:
        company = _resolve(db, ticker)
        return CompanyResponse(
            company=_to_company(company),
            freshness=freshness_for(db, company_id=company.id, source="sec"),
        ).model_dump(mode="json")

    payload = cache.get_or_load("company", [ticker.upper()], loader=_load)
    return CompanyResponse.model_validate(payload)


@router.get("/{ticker}/financials", response_model=FinancialsResponse)
async def get_financials(
    ticker: str,
    metrics: str = Query(default="revenue,net_income"),
    period_type: str = Query(default="FY"),
    from_: int | None = Query(default=None, alias="from"),
    to: int | None = None,
    db: Session = _DB,
) -> FinancialsResponse:
    company = _resolve(db, ticker)
    names = [m.strip() for m in metrics.split(",") if m.strip()]
    rows = metric_repo.get_series_multi(
        db,
        company_id=company.id,
        metric_names=names,
        period_type=period_type,
        from_year=from_,
        to_year=to,
    )
    by_name: dict[str, list[MetricSeriesPoint]] = {name: [] for name in names}
    for row in rows:
        by_name.setdefault(row.metric_name, []).append(
            MetricSeriesPoint(
                period=row.period,
                period_end=row.period_end.isoformat() if row.period_end else None,
                value=row.metric_value,
                unit=row.unit,
            )
        )
    series = [MetricSeries(metric_name=name, points=by_name.get(name, [])) for name in names]
    return FinancialsResponse(
        ticker=company.ticker,
        period_type=period_type,
        series=series,
        freshness=freshness_for(db, company_id=company.id, source="sec"),
    )


@router.get("/{ticker}/metrics/{metric_name}/lineage", response_model=MetricResult)
async def get_metric_lineage(
    ticker: str, metric_name: str, period: str = "FY2025", db: Session = _DB
) -> MetricResult:
    """Show how a derived metric was computed (CIT-003)."""
    company = _resolve(db, ticker)
    row = metric_repo.get_latest_metric(
        db, company_id=company.id, metric_name=metric_name, period=period
    )
    if row is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"no {metric_name} for {company.ticker} {period}"
        )
    return metric_to_result(row)


@router.get("/{ticker}/valuation", response_model=ValuationResponse)
async def get_valuation(ticker: str, db: Session = _DB) -> ValuationResponse:
    company = _resolve(db, ticker)
    rows = metric_repo.get_latest_metrics(
        db, company_id=company.id, metric_names=_VALUATION_METRICS
    )
    return ValuationResponse(
        ticker=company.ticker,
        metrics=[metric_to_result(r) for r in rows],
        freshness=freshness_for(db, company_id=company.id, source="price"),
    )


@router.get("/{ticker}/prices", response_model=PricesResponse)
async def get_prices(
    ticker: str,
    start: str | None = None,
    end: str | None = None,
    interval: str = "1d",
    db: Session = _DB,
) -> PricesResponse:
    company = _resolve(db, ticker)
    start_d = _parse_date(start, "start") or date(1970, 1, 1)
    end_d = _parse_date(end, "end") or date.today()
    bars = price_repo.get_price_history(db, company_id=company.id, start=start_d, end=end_d)
    points = [
        PricePoint(
            date=b.date.isoformat(),
            open=b.open,
            high=b.high,
            low=b.low,
            close=b.close,
            adj_close=b.adj_close,
            volume=b.volume,
        )
        for b in bars
    ]
    return PricesResponse(
        ticker=company.ticker,
        interval=interval,
        points=points,
        freshness=freshness_for(db, company_id=company.id, source="price"),
    )


@router.get("/{ticker}/insiders", response_model=list[InsiderTransaction], tags=["Ownership"])
async def get_insiders(ticker: str, db: Session = _DB) -> list[InsiderTransaction]:
    """Form 4 insider transactions. Not yet ingested (Appendix F #10, P2) → empty."""
    _resolve(db, ticker)
    return []


@router.get("/{ticker}/ownership", response_model=list[OwnershipHolding], tags=["Ownership"])
async def get_ownership(ticker: str, db: Session = _DB) -> list[OwnershipHolding]:
    """13F institutional holdings. Not yet ingested (Appendix F #10, P2) → empty."""
    _resolve(db, ticker)
    return []


@router.get("/{ticker}/filings", response_model=list[FilingSummary], tags=["Filings"])
async def list_company_filings(
    response: Response,
    ticker: str,
    type: str | None = None,
    limit: int | None = None,
    cursor: str | None = None,
    db: Session = _DB,
) -> list[FilingSummary]:
    company = _resolve(db, ticker)
    page_size = clamp_limit(limit)
    rows = filing_repo.list_filings(
        db,
        company_id=company.id,
        filing_type=type,
        limit=page_size + 1,
        after_id=decode_cursor(cursor),
    )
    has_more = len(rows) > page_size
    rows = rows[:page_size]
    if has_more and rows:
        response.headers[NEXT_CURSOR_HEADER] = encode_cursor(rows[-1].id)
    return [
        FilingSummary(
            filing_id=str(f.id),
            filing_type=f.filing_type,
            filing_date=f.filing_date.isoformat() if f.filing_date else None,
            period_end=f.period_end.isoformat() if f.period_end else None,
            accession_number=f.accession_number,
            primary_document_url=f.primary_document_url,
        )
        for f in rows
    ]


@router.get("/{ticker}/earnings", response_model=EarningsResponse, tags=["Filings"])
async def list_earnings_reactions(ticker: str, db: Session = _DB) -> EarningsResponse:
    """Deterministic price move around each earnings 8-K (Item 2.02), newest first (§37.3)."""
    company = _resolve(db, ticker)
    return EarningsResponse(
        ticker=company.ticker,
        method="adjusted close: last session before the filing date -> first session after it",
        events=[
            EarningsReaction(
                filing=to_summary(r.filing),
                pre_date=r.pre_date.isoformat() if r.pre_date else None,
                pre_close=r.pre_close,
                post_date=r.post_date.isoformat() if r.post_date else None,
                post_close=r.post_close,
                move=r.move,
                reason=r.reason,
            )
            for r in earnings_reactions(db, company_id=company.id)
        ],
    )


def _series(
    topic: str, label: str, filing_ids: list[str], tallies: list[topics.Tally], words: list[int]
) -> LanguageSeries:
    flags = topics.flags([t.count for t in tallies])
    return LanguageSeries(
        topic=topic,
        label=label,
        points=[
            LanguagePoint(
                filing_id=filing_id,
                count=tally.count,
                per_1k_words=tally.per_1k(word_count),
                flag=flag,
                statements=[
                    LanguageStatement(source_id=s.source_id, text=s.text, mentions=s.mentions)
                    for s in tally.statements
                ],
            )
            for filing_id, tally, word_count, flag in zip(
                filing_ids, tallies, words, flags, strict=True
            )
        ],
    )


@router.get(
    "/{ticker}/management-language", response_model=ManagementLanguageResponse, tags=["Filings"]
)
async def get_management_language(
    ticker: str,
    filing_type: str = Query(default="10-K", pattern="^10-[KQ]$"),
    limit: int = Query(default=8, ge=2, le=20),
    db: Session = _DB,
) -> ManagementLanguageResponse:
    """Topic intensity and hedging index per filing, from MD&A text (§37.5). Lexicon counts only."""
    company = _resolve(db, ticker)
    filings = filing_repo.list_filings_by_type(db, company_id=company.id, filing_type=filing_type)
    by_document: dict[int, list[DocumentChunk]] = {}
    for chunk in filing_repo.get_section_chunks(
        db,
        document_ids=[f.document_id for f in filings],
        section_like=topics.MDA_SECTION_LIKE,
        parser_version=PARSER_VERSION,
    ):
        by_document.setdefault(chunk.document_id, []).append(chunk)
    # Filings whose MD&A was never parsed are left out rather than charted as zero mentions.
    covered = [f for f in filings if f.document_id in by_document][-limit:]
    analyses = [topics.analyze(by_document[f.document_id]) for f in covered]
    filing_ids = [str(f.id) for f in covered]
    words = [a.word_count for a in analyses]
    return ManagementLanguageResponse(
        ticker=company.ticker,
        taxonomy_version=topics.TOPIC_TAXONOMY_VERSION,
        hedging_lexicon_version=topics.HEDGING_LEXICON_VERSION,
        method="lexicon mention counts in MD&A, per 1,000 words; not an AI judgment",
        periods=[
            LanguagePeriod(
                filing_id=str(f.id),
                filing_type=f.filing_type,
                filing_date=f.filing_date.isoformat() if f.filing_date else None,
                period_end=f.period_end.isoformat() if f.period_end else None,
                word_count=a.word_count,
            )
            for f, a in zip(covered, analyses, strict=True)
        ],
        topics=[
            _series(topic, label, filing_ids, [a.topics[topic] for a in analyses], words)
            for topic, (label, _) in topics.TOPIC_TAXONOMY.items()
        ],
        hedging=_series(
            "hedging", "Hedging language", filing_ids, [a.hedging for a in analyses], words
        ),
    )


@router.get("/{ticker}/news", response_model=NewsResponse, tags=["News"])
async def list_company_news(
    ticker: str,
    category: str | None = None,
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = None,
    source: str | None = None,
    min_relevance: float | None = None,
    limit: int | None = None,
    cursor: str | None = None,
    db: Session = _DB,
) -> NewsResponse:
    company = _resolve(db, ticker)
    page_size = clamp_limit(limit)
    try:
        rel = Decimal(str(min_relevance)) if min_relevance is not None else None
    except InvalidOperation as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid min_relevance") from exc
    rows = news_repo.list_news(
        db,
        company_id=company.id,
        category=category,
        publisher=source,
        from_dt=_parse_dt(from_, "from"),
        to_dt=_parse_dt(to, "to"),
        min_relevance=rel,
        limit=page_size + 1,
        after_id=decode_cursor(cursor),
    )
    has_more = len(rows) > page_size
    rows = rows[:page_size]
    next_cursor = encode_cursor(rows[-1].id) if has_more and rows else None
    doc_ids = [n.document_id for n in rows if n.document_id is not None]
    tiers = news_repo.publisher_tiers(db, doc_ids)
    return NewsResponse(
        ticker=company.ticker,
        items=[
            NewsItem(
                news_id=str(n.id),
                title=n.title,
                description=n.description,
                url=n.url,
                publisher=n.publisher,
                published_at=n.published_at.isoformat() if n.published_at else None,
                category=n.category,
                relevance_score=float(n.relevance_score) if n.relevance_score is not None else None,
                tier=tiers.get(n.document_id) if n.document_id is not None else None,
                cluster_id=n.event_cluster_id,
            )
            for n in rows
        ],
        next_cursor=next_cursor,
        freshness=freshness_for(db, company_id=company.id, source="news"),
    )


@router.get("/{ticker}/research/latest", response_model=ResearchReportEnvelope, tags=["Research"])
async def latest_research(ticker: str, db: Session = _DB) -> ResearchReportEnvelope:
    company = _resolve(db, ticker)
    report = report_repo.get_latest_complete(db, company_id=company.id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no completed report for this company")
    return ResearchReportEnvelope(
        research_id=str(report.id),
        ticker=company.ticker,
        generated_at=report.generated_at.isoformat() if report.generated_at else None,
        model=report.model,
        prompt_version=report.prompt_version,
        data_version=report.data_version,
        report=ResearchReport.model_validate(report.report_json or {}),
    )
