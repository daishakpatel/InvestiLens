"""Canonical-metric builder (Phase 1b).

Reads a company's raw `financial_facts`, applies the concept map (DR-020) and fiscal calendar
(DR-021), and writes canonical `financial_metrics`: annual base values (with restatement rows,
DR-023), derived Q4 flow values (DR-022), and `data_quality_issues` for unit/anomaly problems
(DR-024/028). It does NOT compute ratios/growth — that is Phase 1c.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import cast

from sqlalchemy.orm import Session

from app.finance.concept_map import ConceptMap, load_concept_map
from app.finance.derivation import derive_q4
from app.finance.facts import fact_view_from_orm
from app.finance.periods import (
    derive_fiscal_calendar,
    fiscal_year_of,
    is_full_year,
    is_quarter,
)
from app.finance.selection import (
    FactView,
    Selection,
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

# Flow metrics eligible for Q4 derivation (DR-022). Stock items are instants, never derived.
_Q4_METRICS = ["revenue", "net_income", "operating_income", "operating_cash_flow"]


@dataclass
class BuildCounts:
    annual_metrics: int = 0
    derived_q4: int = 0
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


def _annual_fyes(facts: list[FactView], revenue_tags: list[str], fye_month: int) -> list[date]:
    """Fiscal year-end dates = full-year revenue ends in the FYE month (drops calendar frames)."""
    ends = {
        f.period_end
        for f in facts
        if f.concept_tag in revenue_tags
        and f.period_end
        and f.period_end.month == fye_month
        and is_full_year(f.period_start, f.period_end)
    }
    return sorted(e for e in ends if e is not None)


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
    session: Session, company_id: int, facts: list[FactView], cmap: ConceptMap, fye_month: int
) -> int:
    revenue_tags = cmap.tags("revenue")
    annual = sorted(
        {
            (f.period_start, f.period_end)
            for f in facts
            if f.concept_tag in revenue_tags
            and f.period_start
            and f.period_end
            and f.period_end.month == fye_month
            and is_full_year(f.period_start, f.period_end)
        },
        key=lambda s: s[1],
    )
    quarterly = _quarter_spans(facts, revenue_tags)
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
            source_id=fact.accession_number,
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


def _derive_quarter_four(
    session: Session,
    *,
    company_id: int,
    facts: list[FactView],
    cmap: ConceptMap,
    fye: date,
    fiscal_year: int,
    quarter_ends: list[date],
    fye_month: int,
) -> int:
    """Derive Q4 = FY - (Q1+Q2+Q3) for flow metrics where all quarters exist (DR-022)."""
    quarters = [e for e in quarter_ends if fiscal_year_of(e, fye_month) == fiscal_year][:3]
    if len(quarters) < 3:
        return 0
    derived = 0
    for metric in _Q4_METRICS:
        fy = select_metric(facts, cmap, metric, period_end=fye)
        q = [select_metric(facts, cmap, metric, period_end=qe, quarter=True) for qe in quarters]
        if fy is None or any(s is None for s in q):
            continue
        q1, q2, q3 = cast(tuple[Selection, Selection, Selection], tuple(q))
        result = derive_q4(fy, q1, q2, q3)
        metrics_repo.upsert_metric(
            session,
            company_id=company_id,
            period=f"Q4-FY{fiscal_year}",
            fiscal_year=fiscal_year,
            fiscal_quarter=4,
            period_start=None,
            period_end=fye,
            period_type="Q",
            metric_name=metric,
            metric_value=result.value,
            unit=fy.unit,
            is_derived=True,
            source_tag=fy.source_tag,
            source_id=f"q4_derived:{metric}",
            as_reported_accession=None,
            is_latest=True,
            quality_flags={"derived": "Q4=FY-(Q1+Q2+Q3)", "inputs": result.input_accessions},
        )
        derived += 1
    return derived


def build_company_metrics(session: Session, company: Company) -> BuildCounts:
    """Build canonical metrics, fiscal calendar, and quality issues for one company."""
    cmap = load_concept_map(ticker=company.ticker, cik=company.cik, sector=company.sector)
    facts = [fact_view_from_orm(f) for f in facts_repo.facts_for_company(session, company.id)]
    counts = BuildCounts()

    revenue_tags = cmap.tags("revenue")
    fye_month = _fye_month(facts, revenue_tags)

    metrics_repo.clear_company_metrics(session, company.id)
    counts.fiscal_periods = _build_fiscal_calendar(session, company.id, facts, cmap, fye_month)

    quarter_ends = sorted({e for _, e in _quarter_spans(facts, revenue_tags)})

    for fye in _annual_fyes(facts, revenue_tags, fye_month):
        fiscal_year = fiscal_year_of(fye, fye_month)
        for metric in cmap.flow_metrics + cmap.stock_metrics:
            rows, issues = _persist_annual_metric(
                session,
                company_id=company.id,
                facts=facts,
                cmap=cmap,
                metric=metric,
                fye=fye,
                fiscal_year=fiscal_year,
            )
            counts.annual_metrics += rows
            counts.quality_issues += issues
        counts.derived_q4 += _derive_quarter_four(
            session,
            company_id=company.id,
            facts=facts,
            cmap=cmap,
            fye=fye,
            fiscal_year=fiscal_year,
            quarter_ends=quarter_ends,
            fye_month=fye_month,
        )

    return counts
