"""Deterministic side-by-side company comparison (§37.1).

Pure backend math (no LLM): gather each company's FY metrics, calendarize them onto a common
calendar year, and compute each company's sector-normalized percentile versus the peer set using
the Phase 1c `percentile_rank` utility. The real logic behind the `compare_companies` tool (§16.7)
and the `/compare` endpoint. AI commentary lives in `commentary.py` and consumes what `gather`
returns, so prose is always a view over these exact verified numbers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy.orm import Session

from app.api._support import metric_to_result
from app.comparison.calendar import (
    calendarized,
    fiscal_year_end_month,
    latest_common_year,
    row_calendar_year,
)
from app.finance.metrics import percentile_rank
from app.models import Company, FinancialMetric
from app.repositories import companies as company_repo
from app.repositories import metrics as metric_repo
from app.schemas.comparison import (
    DEFAULT_COMPARISON_METRICS,
    ComparisonCell,
    ComparisonCompany,
    ComparisonMetricRow,
    ComparisonResponse,
)
from app.schemas.sources import MetricResult

_YEAR = re.compile(r"(\d{4})")


@dataclass
class GatheredComparison:
    """The calendarized, resolved inputs both the deterministic response and commentary build on."""

    companies: list[Company]
    metric_names: list[str]
    target_year: int | None
    # company id → metric name → {calendar year: chosen row}
    rows: dict[int, dict[str, dict[int, FinancialMetric]]]
    notes: list[str] = field(default_factory=list)

    def selected(self, company: Company, metric_name: str) -> FinancialMetric | None:
        if self.target_year is None:
            return None
        return self.rows[company.id].get(metric_name, {}).get(self.target_year)


def _target_year(period: str | None, per_company_years: list[set[int]]) -> int | None:
    """Resolve the comparison calendar year: an explicit year in `period`, else latest common."""
    if period and (match := _YEAR.search(period)):
        return int(match.group(1))
    return latest_common_year(per_company_years)


def gather(
    session: Session,
    tickers: list[str],
    *,
    metrics: list[str] | None = None,
    period: str | None = None,
) -> GatheredComparison:
    """Resolve companies, fetch + calendarize their FY metrics, and pick the comparison year."""
    metric_names = list(metrics) if metrics else list(DEFAULT_COMPARISON_METRICS)
    resolved = company_repo.get_many_by_ticker(session, tickers)
    ordered: list[Company] = []
    for t in tickers:
        company = resolved.get(t.upper())
        if company is None:
            raise ValueError(f"unknown ticker: {t}")
        if company not in ordered:
            ordered.append(company)

    rows: dict[int, dict[str, dict[int, FinancialMetric]]] = {}
    year_sets: list[set[int]] = []
    for company in ordered:
        fetched = metric_repo.get_series_multi(
            session, company_id=company.id, metric_names=metric_names, period_type="FY"
        )
        fye_month = fiscal_year_end_month(company)
        by_metric: dict[str, list[FinancialMetric]] = {}
        for row in fetched:
            by_metric.setdefault(row.metric_name, []).append(row)
        rows[company.id] = {m: calendarized(rs, fye_month) for m, rs in by_metric.items()}
        years: set[int] = set()
        for cal_map in rows[company.id].values():
            years |= set(cal_map.keys())
        year_sets.append(years)

    notes: list[str] = []
    target = _target_year(period, year_sets)
    if target is None:
        notes.append("No overlapping calendar year across the selected companies.")
    return GatheredComparison(
        companies=ordered, metric_names=metric_names, target_year=target, rows=rows, notes=notes
    )


def compare_companies(
    session: Session,
    tickers: list[str],
    *,
    metrics: list[str] | None = None,
    period: str | None = None,
) -> ComparisonResponse:
    """Compare `tickers` across `metrics` for a calendarized `period` (default: latest common)."""
    g = gather(session, tickers, metrics=metrics, period=period)
    return build_response(g)


def build_response(g: GatheredComparison) -> ComparisonResponse:
    """Project a gathered comparison into the API/tool response (percentiles + alignment info)."""
    companies_out: list[ComparisonCompany] = []
    for company in g.companies:
        fye_month = fiscal_year_end_month(company)
        anchor = _anchor_row(g, company)
        companies_out.append(
            ComparisonCompany(
                ticker=company.ticker,
                name=company.name,
                sic_code=company.sic_code,
                sector=company.sector,
                fiscal_year_end=company.fiscal_year_end,
                fiscal_period=anchor.period if anchor else None,
                calendar_year=(row_calendar_year(anchor, fye_month) if anchor else None),
                period_end=(
                    anchor.period_end.isoformat() if anchor and anchor.period_end else None
                ),
            )
        )

    metric_rows = [_build_row(g, metric_name) for metric_name in g.metric_names]
    return ComparisonResponse(
        calendar_year=g.target_year,
        companies=companies_out,
        metrics=metric_rows,
        notes=list(g.notes),
    )


def _anchor_row(g: GatheredComparison, company: Company) -> FinancialMetric | None:
    """A representative row at the target year (prefer revenue), for the period label."""
    for preferred in ("revenue", "net_income"):
        row = g.selected(company, preferred)
        if row is not None:
            return row
    if g.target_year is not None:
        for cal_map in g.rows[company.id].values():
            if g.target_year in cal_map:
                return cal_map[g.target_year]
    return None


def _missing_cell(ticker: str, metric_name: str) -> ComparisonCell:
    return ComparisonCell(
        ticker=ticker,
        result=MetricResult(
            value=None, unit="", formula_id=metric_name, warnings=["NO_DATA_FOR_PERIOD"]
        ),
        percentile=None,
    )


def _build_row(g: GatheredComparison, metric_name: str) -> ComparisonMetricRow:
    """Build one metric row's cells and each company's percentile vs the peer distribution."""
    selected: dict[str, FinancialMetric | None] = {}
    unit = ""
    for company in g.companies:
        row = g.selected(company, metric_name)
        selected[company.ticker] = row
        if row is not None:
            unit = row.unit

    # Sector-normalized percentile: distribution = the peer set's non-null values for this metric.
    distribution = [
        r.metric_value for r in selected.values() if r is not None and r.metric_value is not None
    ]

    cells: list[ComparisonCell] = []
    for company in g.companies:
        row = selected[company.ticker]
        if row is None:
            cells.append(_missing_cell(company.ticker, metric_name))
            continue
        pct: Decimal | None = None
        if row.metric_value is not None and len(distribution) > 1:
            pct = percentile_rank(row.metric_value, distribution).value
        cells.append(
            ComparisonCell(ticker=company.ticker, result=metric_to_result(row), percentile=pct)
        )
    return ComparisonMetricRow(metric_name=metric_name, unit=unit, cells=cells)
