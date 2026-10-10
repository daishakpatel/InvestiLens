"""Portfolio analysis orchestrator (§37.2).

Resolves holdings, gathers per-company metrics/sector/prices, and assembles the deterministic
aggregates plus the per-holding data the client needs for what-if recompute. All numbers are
backend math; the output is analysis, never advice (LGL-006).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.api._support import metric_to_result
from app.portfolio import metrics as pmetrics
from app.portfolio import themes as pthemes
from app.portfolio.risk import build_risk_stats
from app.portfolio.weights import normalize
from app.repositories import companies as company_repo
from app.repositories import metrics as metric_repo
from app.repositories import prices as price_repo
from app.schemas.portfolio import (
    HoldingData,
    NormalizedHolding,
    PortfolioAnalysis,
    PortfolioRequest,
)

# Ratio-type metrics that weight sensibly across a portfolio (§37.2 "weighted metrics").
DEFAULT_PORTFOLIO_METRICS: tuple[str, ...] = (
    "gross_margin",
    "operating_margin",
    "net_margin",
    "fcf_margin",
    "yoy_growth",
    "roe",
    "debt_to_equity",
    "pe_ratio",
)

_PRICE_LOOKBACK_DAYS = 730  # ~2 calendar years of daily bars for volatility/correlation


def analyze(
    session: Session, request: PortfolioRequest, *, today: date | None = None
) -> PortfolioAnalysis:
    """Analyze a hypothetical portfolio of 1+ holdings (deterministic; non-advisory)."""
    weights = normalize(request.holdings)
    metric_names = list(request.metrics) if request.metrics else list(DEFAULT_PORTFOLIO_METRICS)
    today = today or date.today()

    companies = company_repo.get_many_by_ticker(session, [w.ticker for w in weights])
    notes: list[str] = []
    unknown = [w.ticker for w in weights if w.ticker not in companies]
    if unknown:
        raise ValueError(f"unknown ticker(s): {', '.join(unknown)}")

    sectors: dict[str, str | None] = {}
    values_by_metric: dict[str, dict[str, Decimal | None]] = {m: {} for m in metric_names}
    units: dict[str, str] = {m: "" for m in metric_names}
    holdings_data: list[HoldingData] = []
    prices: dict[str, list[tuple[date, Decimal]]] = {}

    for w in weights:
        company = companies[w.ticker]
        sectors[w.ticker] = company.sector
        rows = metric_repo.get_latest_metrics(
            session, company_id=company.id, metric_names=metric_names
        )
        by_name = {r.metric_name: r for r in rows}
        holding_metrics = {}
        for m in metric_names:
            row = by_name.get(m)
            values_by_metric[m][w.ticker] = row.metric_value if row is not None else None
            if row is not None and row.unit:
                units[m] = row.unit
            if row is not None:
                holding_metrics[m] = metric_to_result(row)

        series = _price_series(session, company.id, today)
        prices[w.ticker] = series
        holdings_data.append(
            HoldingData(ticker=w.ticker, sector=company.sector, metrics=holding_metrics)
        )

    weighted = [
        pmetrics.weighted_metric(m, units[m], values_by_metric[m], weights) for m in metric_names
    ]
    sector_exposure = pmetrics.sector_exposure(sectors, weights)
    concentration = pmetrics.concentration(weights)

    window_start = today - timedelta(days=_PRICE_LOOKBACK_DAYS)
    risk_stats = build_risk_stats(prices, weights, window_start=window_start, window_end=today)
    # Thread each holding's annualized volatility into holdings_data for client-side recompute.
    vol_by_ticker = {hv.ticker: hv.annualized_volatility for hv in risk_stats.holding_volatility}
    for hd in holdings_data:
        hd.annualized_volatility = vol_by_ticker.get(hd.ticker)

    risk_themes, missing_reports = pthemes.aggregate_themes(session, weights)
    if missing_reports:
        notes.append(
            "No completed research report for: "
            f"{', '.join(missing_reports)} — risk themes exclude them."
        )

    return PortfolioAnalysis(
        holdings=[
            NormalizedHolding(
                ticker=w.ticker,
                name=companies[w.ticker].name,
                weight=w.weight,
                sector=companies[w.ticker].sector,
            )
            for w in weights
        ],
        weighted_metrics=weighted,
        sector_exposure=sector_exposure,
        concentration=concentration,
        risk_stats=risk_stats,
        risk_themes=risk_themes,
        holdings_data=holdings_data,
        notes=notes,
    )


def _price_series(session: Session, company_id: int, today: date) -> list[tuple[date, Decimal]]:
    start = today - timedelta(days=_PRICE_LOOKBACK_DAYS)
    bars = price_repo.get_price_history(session, company_id=company_id, start=start, end=today)
    series: list[tuple[date, Decimal]] = []
    for b in bars:
        price = b.adj_close if b.adj_close is not None else b.close
        if price is not None and price > 0:
            series.append((b.date, price))
    return series
