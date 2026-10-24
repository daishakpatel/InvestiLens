"""Canonical-metric builder (Phase 1b).

Reads a company's raw `financial_facts`, applies the concept map (DR-020) and fiscal calendar
(DR-021), and writes canonical `financial_metrics`: annual base values (with restatement rows,
DR-023), and `data_quality_issues` for unit/anomaly problems (DR-024/028). Quarterly and TTM
rows, and the `metric_gaps` they leave, come from `quarterly_builder` over the same facts (Phase
7b, ADR-0040). Annual ratios/growth are Phase 1c (`ratio_builder`).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.finance.concept_map import ConceptMap, load_concept_map
from app.finance.facts import fact_view_from_orm, with_composites
from app.finance.periods import (
    derive_fiscal_calendar,
    fiscal_year_of,
    is_full_year,
    is_quarter,
)
from app.finance.quarterly_builder import build_quarterly_metrics
from app.finance.selection import (
    FactView,
    matching_facts,
    rank_restatements,
    select_metric,
)
from app.finance.validation import check_nonnegative, check_unit
from app.models import Company
from app.repositories import facts as facts_repo
from app.repositories import fiscal as fiscal_repo
from app.repositories import metrics as metrics_repo
from app.repositories import quality as quality_repo


@dataclass
class BuildCounts:
    annual_metrics: int = 0
    quarterly_metrics: int = 0
    ttm_metrics: int = 0
    metric_gaps: int = 0
    fiscal_periods: int = 0
    quality_issues: int = 0


def _fye_month(facts: list[FactView], revenue_tags: list[str]) -> int:
    """The company's fiscal-year-end month = modal month of annual revenue ends (DR-021).

    This distinguishes the fiscal year (e.g. NVIDIA's January end) from calendar-aligned frames
    (December), so non-December fiscal years are labelled correctly.
    """
    months = [
        f.period_end.month
        for f in facts
        if f.concept_tag in revenue_tags
        and f.period_end
        and is_full_year(f.period_start, f.period_end)
    ]
    return Counter(months).most_common(1)[0][0] if months else 12


def _annual_spans(
    facts: list[FactView], revenue_tags: list[str], fye_month: int
) -> list[tuple[date, date]]:
    """Fiscal-year (start, end) spans = full-year revenue periods ending in the FYE month (drops
    calendar-aligned frames), oldest first."""
    spans = {
        (f.period_start, f.period_end)
        for f in facts
        if f.concept_tag in revenue_tags
        and f.period_start
        and f.period_end
        and f.period_end.month == fye_month
        and is_full_year(f.period_start, f.period_end)
    }
    return sorted(spans, key=lambda s: s[1])


def _annual_fyes(spans: list[tuple[date, date]]) -> list[date]:
    """Fiscal year-end dates, one per year."""
    return sorted({end for _, end in spans})


def _quarter_spans(facts: list[FactView], revenue_tags: list[str]) -> list[tuple[date, date]]:
    spans = {
        (f.period_start, f.period_end)
        for f in facts
        if f.concept_tag in revenue_tags
        and f.period_start
        and f.period_end
        and is_quarter(f.period_start, f.period_end)
    }
    return sorted(spans, key=lambda s: s[1])


def _build_fiscal_calendar(
    session: Session,
    company_id: int,
    facts: list[FactView],
    cmap: ConceptMap,
    fye_month: int,
    annual: list[tuple[date, date]],
) -> int:
    quarterly = _quarter_spans(facts, cmap.tags("revenue"))
    fiscal_repo.clear_company_fiscal_calendars(session, company_id)  # idempotent rebuild
    periods = derive_fiscal_calendar(annual, quarterly, fye_month)
    for p in periods:
        fiscal_repo.upsert_fiscal_period(
            session,
            company_id=company_id,
            fiscal_year=p.fiscal_year,
            fiscal_quarter=p.fiscal_quarter,
            period_start=p.period_start,
            period_end=p.period_end,
            period_type=p.period_type,
            weeks_in_period=p.weeks_in_period,
        )
    return len(periods)


def _persist_annual_metric(
    session: Session,
    *,
    company_id: int,
    ticker: str,
    facts: list[FactView],
    cmap: ConceptMap,
    metric: str,
    fye: date,
    fiscal_year: int,
) -> tuple[int, int]:
    """Persist a canonical annual metric (with restatement rows). Returns (rows, issues)."""
    selection = select_metric(facts, cmap, metric, period_end=fye)
    if selection is None:
        return 0, 0
    kind = cmap.kind(metric) or "flow"
    candidates = matching_facts(facts, selection.source_tag, period_end=fye, kind=kind)
    rows = 0
    issues = 0
    for fact, is_latest in rank_restatements(candidates):
        metrics_repo.upsert_metric(
            session,
            company_id=company_id,
            period=f"FY{fiscal_year}",
            fiscal_year=fiscal_year,
            fiscal_quarter=None,
            period_start=fact.period_start,
            period_end=fact.period_end,
            period_type="FY",
            metric_name=metric,
            metric_value=fact.value,
            unit=fact.unit,
            source_tag=selection.source_tag,
            # One ID per metric and period: the filing's accession number alone is shared by
            # every metric that filing reports, so it cannot say which one is cited (ADR-0034).
            source_id=f"xbrl:{ticker}:{metric}:FY{fiscal_year}",
            as_reported_accession=fact.accession_number,
            is_latest=is_latest,
        )
        rows += 1
    # DR-024 unit check + DR-028 non-negative revenue, on the latest value.
    unit_issue = check_unit(
        metric, selection.unit, cmap.unit_family(metric), period=f"FY{fiscal_year}"
    )
    if unit_issue:
        quality_repo.record_issue(
            session,
            company_id=company_id,
            metric_name=metric,
            period=f"FY{fiscal_year}",
            issue_code=unit_issue.issue_code,
            details=unit_issue.details,
        )
        issues += 1
    if metric == "revenue":
        neg = check_nonnegative(metric, selection.value, period=f"FY{fiscal_year}")
        if neg:
            quality_repo.record_issue(
                session,
                company_id=company_id,
                metric_name=metric,
                period=f"FY{fiscal_year}",
                issue_code=neg.issue_code,
                details=neg.details,
            )
            issues += 1
    return rows, issues


def build_company_metrics(session: Session, company: Company) -> BuildCounts:
    """Build canonical metrics, fiscal calendar, and quality issues for one company."""
    cmap = load_concept_map(ticker=company.ticker, cik=company.cik, sector=company.sector)
    facts = with_composites(
        [fact_view_from_orm(f) for f in facts_repo.facts_for_company(session, company.id)],
        cmap.composites,
    )
    counts = BuildCounts()

    revenue_tags = cmap.tags("revenue")
    fye_month = _fye_month(facts, revenue_tags)

    annual = _annual_spans(facts, revenue_tags, fye_month)

    metrics_repo.clear_company_metrics(session, company.id)
    counts.fiscal_periods = _build_fiscal_calendar(
        session, company.id, facts, cmap, fye_month, annual
    )

    for fye in _annual_fyes(annual):
        fiscal_year = fiscal_year_of(fye, fye_month)
        for metric in cmap.flow_metrics + cmap.stock_metrics:
            rows, issues = _persist_annual_metric(
                session,
                company_id=company.id,
                ticker=company.ticker,
                facts=facts,
                cmap=cmap,
                metric=metric,
                fye=fye,
                fiscal_year=fiscal_year,
            )
            counts.annual_metrics += rows
            counts.quality_issues += issues

    quarterly = build_quarterly_metrics(session, company, facts, cmap, annual, fye_month)
    counts.quarterly_metrics = quarterly.quarterly
    counts.ttm_metrics = quarterly.ttm
    counts.metric_gaps = quarterly.gaps
    return counts
