"""Report-level evaluation (spec §18.8): section completeness, citation coverage, rejected-claim
rate, cost, latency. MEASURES a generated ResearchReport; it does not generate one.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.schemas.research import ResearchReport

# The 12 content sections a complete report covers (§10).
_CLAIM_SECTIONS = (
    "executive_summary",
    "company_overview",
    "revenue_analysis",
    "profitability_analysis",
    "balance_sheet_analysis",
    "cash_flow_analysis",
    "valuation_analysis",
)
_OTHER_SECTIONS = ("news_summary", "risks", "management_commentary", "bull_factors", "bear_factors")
_TOTAL_SECTIONS = len(_CLAIM_SECTIONS) + len(_OTHER_SECTIONS)


@dataclass(frozen=True)
class ReportEval:
    section_completeness: float  # fraction of sections with ≥1 item
    citation_coverage: float  # fraction of claim-sentences carrying ≥1 source (invariant: 1.0)
    total_claims: int
    rejected_claim_rate: float | None  # from verification (accepted vs rejected), if supplied
    cost_usd: Decimal | None
    latency_ms: int | None


def _claim_units(report: ResearchReport) -> list[list[str]]:
    """Each citable unit's source_ids (claims, risks, news, management, factor claims)."""
    units: list[list[str]] = []
    for name in _CLAIM_SECTIONS:
        units += [c.source_ids for c in getattr(report, name)]
    units += [n.source_ids for n in report.news_summary]
    units += [r.source_ids for r in report.risks]
    units += [m.source_ids for m in report.management_commentary]
    for factor in [*report.bull_factors, *report.bear_factors]:
        units += [c.source_ids for c in factor.claims]
    return units


def evaluate_report(
    report: ResearchReport,
    *,
    accepted_claims: int | None = None,
    rejected_claims: int | None = None,
    cost_usd: Decimal | None = None,
    latency_ms: int | None = None,
) -> ReportEval:
    non_empty = sum(1 for name in (*_CLAIM_SECTIONS, *_OTHER_SECTIONS) if getattr(report, name))
    units = _claim_units(report)
    cited = sum(1 for ids in units if ids)
    total_verified = (
        (accepted_claims or 0) + (rejected_claims or 0)
        if accepted_claims is not None or rejected_claims is not None
        else 0
    )
    return ReportEval(
        section_completeness=non_empty / _TOTAL_SECTIONS,
        citation_coverage=cited / len(units) if units else 0.0,
        total_claims=len(units),
        rejected_claim_rate=(rejected_claims or 0) / total_verified if total_verified else None,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
    )
