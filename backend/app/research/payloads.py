"""Deterministic financial payloads for the section generators (§10.3, DR: no LLM math).

Each payload is JSON the LLM only *explains* — every number is computed here in Decimal from
`financial_metrics` (Phase 1c), with an explicit unit, and N/A-labeled when a metric is NULL (e.g.
bank-inapplicable metrics for JPM, DR-041/042). Alongside the payload we return the `EvidenceItem`s
whose source IDs the payload exposes, so a claim citing a number verifies against the exact value.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.citation.evidence import EvidenceItem
from app.finance import metrics as fin
from app.repositories import metrics as metric_repo
from app.research.evidence import from_metric, metric_source_id

# Metric names per section (canonical `financial_metrics.metric_name` values from Phase 1b/1c).
SECTION_METRICS: dict[str, list[str]] = {
    "executive_summary": ["revenue", "gross_margin"],
    "revenue_analysis": ["revenue"],
    "profitability_analysis": ["gross_margin", "operating_margin", "net_margin", "ebitda"],
    "balance_sheet_analysis": ["total_debt", "debt_to_equity", "current_ratio"],
    "cash_flow_analysis": ["free_cash_flow", "fcf_margin", "capex_intensity", "sbc_pct_revenue"],
    "valuation_analysis": ["market_cap", "pe_ratio", "ps_ratio"],
}

_NA = "N/A"


def _series_block(
    session: Session, company_id: int, name: str
) -> tuple[dict[str, Any], list[EvidenceItem]]:
    rows = metric_repo.get_metric_series(session, company_id=company_id, metric_name=name)
    if not rows:
        return {}, []
    unit = rows[0].unit
    series: dict[str, str] = {}
    source_ids: dict[str, str] = {}
    evidence: list[EvidenceItem] = []
    for row in rows:
        series[row.period] = _NA if row.metric_value is None else str(row.metric_value)
        sid = metric_source_id(row)
        source_ids[row.period] = sid
        evidence.append(from_metric(row))
    block: dict[str, Any] = {"unit": unit, "series": series, "source_ids": source_ids}

    # Deterministic growth (backend math, never the LLM): YoY of the last pair + full-span CAGR.
    valued = [
        (r.fiscal_year, r.metric_value, metric_source_id(r))
        for r in rows
        if r.metric_value is not None
    ]
    if name == "revenue" and len(valued) >= 2:
        calc, calc_ev = _growth_block(valued)
        if calc:
            block["calculated"] = calc
            evidence.extend(calc_ev)
    return block, evidence


def _growth_block(
    valued: list[tuple[int | None, Decimal, str]],
) -> tuple[dict[str, Any], list[EvidenceItem]]:
    (_, prior, prior_sid), (last_fy, last, last_sid) = valued[-2], valued[-1]
    (_, first, first_sid) = valued[0]
    years = (last_fy or 0) - (valued[0][0] or 0)
    yoy = fin.yoy_growth(last, prior)
    out: dict[str, Any] = {}
    evidence: list[EvidenceItem] = []
    if yoy.value is not None:
        out["yoy"] = {"value": str(yoy.value), "unit": "ratio", "source_ids": [last_sid, prior_sid]}
        evidence.append(_derived_ev(f"derived:revenue_yoy_FY{last_fy}", "yoy_growth", yoy.value))
    if years >= 2:
        cagr = fin.cagr(first, last, years)
        if cagr.value is not None:
            out["cagr"] = {
                "value": str(cagr.value),
                "unit": "ratio",
                "years": years,
                "source_ids": [first_sid, last_sid],
            }
            evidence.append(_derived_ev(f"derived:revenue_cagr_FY{last_fy}", "cagr", cagr.value))
    return out, evidence


def _derived_ev(source_id: str, formula_id: str, value: Decimal) -> EvidenceItem:
    from app.schemas.sources import DerivedMetricSource

    return EvidenceItem(
        source=DerivedMetricSource(
            source_id=source_id, tier=1, formula_id=formula_id, formula_version="v1", value=value
        ),
        text=f"{formula_id} = {value}",
        retrieval_score=0.9,
    )


def build_payload(
    session: Session, company_id: int, section: str
) -> tuple[dict[str, Any], list[EvidenceItem]]:
    """Return (financial JSON payload, metric evidence items) for a section. Empty if no metrics."""
    names = SECTION_METRICS.get(section, [])
    metrics: dict[str, Any] = {}
    evidence: list[EvidenceItem] = []
    for name in names:
        block, ev = _series_block(session, company_id, name)
        if block:
            metrics[name] = block
            evidence.extend(ev)
    return ({"metrics": metrics} if metrics else {}), evidence
