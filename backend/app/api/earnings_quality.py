"""Earnings-quality dashboard endpoint (Phase 7d, FR-EQ-009/010).

Read-only over rows `quality_builder` stored: each measure per fiscal year with its status
(ok | insufficient_data | not_applicable), band, inputs and a static explanation. Peer context uses
the Phase 6a peer set and `percentile_rank`, and is withheld below three peers.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api._support import freshness_for, metric_to_result
from app.api.companies import _resolve
from app.comparison.peers import suggest_peers
from app.db import get_db
from app.finance.concept_map import load_concept_map
from app.finance.metrics import NOT_APPLICABLE_SECTOR, percentile_rank
from app.finance.quality_builder import QUALITY_METRICS
from app.finance.quality_catalog import (
    DEFAULT_NOT_APPLICABLE,
    MEASURES,
    NOT_APPLICABLE_REASONS,
    SCREENING_CAVEAT,
)
from app.models import FinancialMetric
from app.repositories import companies as company_repo
from app.repositories import metrics as metric_repo
from app.schemas.earnings_quality import (
    EarningsQualityResponse,
    QualityMeasure,
    QualityPoint,
    QualityStatus,
)

router = APIRouter(prefix="/companies", tags=["Company"])

_DB = Depends(get_db, scope="function")
MIN_PEERS = 3  # a percentile among two companies is noise (FR-EQ-010)
_TTM_MEASURES = ("accruals_ratio", "fcf_conversion")
_DETAIL_KEYS = ("indices", "threshold", "model_variant", "variant_basis", "criteria", "computable")


def to_point(row: FinancialMetric, not_applicable_text: str) -> QualityPoint:
    """A stored row as a dashboard point: NULL is never shown as zero (DR-041/042)."""
    flags = row.quality_flags or {}
    result = metric_to_result(row)
    reason = result.warnings[0] if result.warnings else None
    status: QualityStatus
    if result.value is not None:
        status, reason_text = "ok", None
    elif reason == NOT_APPLICABLE_SECTOR:
        status, reason_text = "not_applicable", not_applicable_text
    else:
        status, reason_text = "insufficient_data", None
    stored_missing = flags.get("missing")
    missing = (
        [str(m) for m in stored_missing]
        if stored_missing
        else [i.name for i in result.inputs if i.value is None and status == "insufficient_data"]
    )
    band = flags.get("band")
    return QualityPoint(
        period=row.period,
        fiscal_year=row.fiscal_year or 0,
        value=result.value,
        status=status,
        band=None if status == "not_applicable" else (str(band) if band else None),
        reason=reason,
        reason_text=reason_text,
        missing=missing,
        source_id=row.source_id,
        formula_id=row.formula_id,
        inputs=result.inputs,
        details={k: flags[k] for k in _DETAIL_KEYS if k in flags},
    )


def _peer_context(
    db: Session, peer_ids: list[int], latest: dict[str, QualityPoint]
) -> dict[str, tuple[Decimal | None, int]]:
    """Per measure: the target's percentile among peers reporting it, and how many do."""
    values = metric_repo.latest_annual_values(
        db, company_ids=peer_ids, metric_names=list(QUALITY_METRICS)
    )
    out: dict[str, tuple[Decimal | None, int]] = {}
    for name in QUALITY_METRICS:
        peer_values = [
            row.metric_value
            for pid in peer_ids
            if (row := values.get((pid, name))) is not None and row.metric_value is not None
        ]
        point = latest.get(name)
        if point is None or point.value is None or len(peer_values) < MIN_PEERS:
            out[name] = (None, len(peer_values))
            continue
        pct = percentile_rank(point.value, [point.value, *peer_values]).value
        out[name] = (pct, len(peer_values))
    return out


@router.get("/{ticker}/earnings-quality", response_model=EarningsQualityResponse)
def get_earnings_quality(
    ticker: str,
    years: int = Query(default=5, ge=1, le=10, description="Latest N fiscal years"),
    db: Session = _DB,
) -> EarningsQualityResponse:
    """Accruals, cash conversion, working-capital days, dilution and the screening scores, per
    fiscal year, each with its inputs' source IDs (FR-EQ-009)."""
    company = _resolve(db, ticker)
    cmap = load_concept_map(ticker=company.ticker, cik=company.cik, sector=company.sector)
    na_text = NOT_APPLICABLE_REASONS.get(cmap.sector, DEFAULT_NOT_APPLICABLE)
    rows = metric_repo.get_series_multi(
        db, company_id=company.id, metric_names=list(QUALITY_METRICS), period_type="FY"
    )
    units = {r.metric_name: r.unit for r in rows}
    fiscal_years = sorted({r.fiscal_year for r in rows if r.fiscal_year is not None})[-years:]
    points: dict[str, list[QualityPoint]] = {name: [] for name in QUALITY_METRICS}
    for row in rows:
        if row.fiscal_year in fiscal_years:
            points[row.metric_name].append(to_point(row, na_text))
    ttm: dict[str, QualityPoint] = {}
    for row in metric_repo.get_series_multi(
        db, company_id=company.id, metric_names=list(_TTM_MEASURES), period_type="TTM"
    ):
        ttm[row.metric_name] = to_point(row, na_text)  # oldest first: the last one wins

    peers = suggest_peers(db, company.ticker).peers
    peer_ids = [
        found.id for p in peers if (found := company_repo.get_by_ticker(db, p.ticker)) is not None
    ]
    latest = {name: pts[-1] for name, pts in points.items() if pts}
    context = _peer_context(db, peer_ids, latest)
    notes = []
    if len(peer_ids) < MIN_PEERS:
        notes.append(
            f"Peer percentiles are hidden: {len(peer_ids)} comparable companies are held, "
            f"{MIN_PEERS} are needed."
        )

    measures = []
    for name in QUALITY_METRICS:
        text = MEASURES[name]
        pts = points[name]
        pct, count = context[name]
        measures.append(
            QualityMeasure(
                metric_name=name,
                label=text.label,
                unit=units.get(name, ""),
                explanation=text.explanation,
                caveat=SCREENING_CAVEAT if text.screening else None,
                points=pts,
                latest_ttm=ttm.get(name),
                peer_percentile=pct,
                peer_count=count,
            )
        )
    return EarningsQualityResponse(
        ticker=company.ticker,
        fiscal_years=fiscal_years,
        measures=measures,
        peers=[p.ticker for p in peers],
        notes=notes,
        freshness=freshness_for(db, company_id=company.id, source="sec"),
    )
