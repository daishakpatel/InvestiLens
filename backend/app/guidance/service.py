"""Guidance responses assembled from stored rows (FR-GD-011/014/016). Read-only; no model call."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.guidance import outcomes
from app.guidance.builder import guided
from app.guidance.taxonomy import label
from app.models import Company, Document, GuidanceItem, GuidanceOutcome
from app.repositories import guidance as repo
from app.schemas.guidance import (
    GuidanceOutcomeView,
    GuidanceRelease,
    GuidanceResponse,
    GuidanceRow,
    GuidanceTrackRecord,
    GuidanceValue,
    TrackRecordQuarter,
)

SCOPE = (
    "Company guidance from its own earnings releases only. Analyst consensus estimates are not "
    "licensed, so results are never compared with them."
)
EXPLANATIONS = {
    "non_gaap_basis": "Guided on a non-GAAP basis; GAAP actual not comparable.",
    "basis_unspecified": "Basis (GAAP or non-GAAP) not stated; not compared with the GAAP actual.",
    "actual_not_reported": "Actual not reported yet.",
}

Row = tuple[GuidanceItem, GuidanceOutcome | None, Document]


def period_label(item: GuidanceItem) -> str:
    fy = f"FY{item.fiscal_year}"
    return fy if item.fiscal_period == "FY" else f"{item.fiscal_period} {fy}"


def _outcome(outcome: GuidanceOutcome | None) -> GuidanceOutcomeView | None:
    if outcome is None:
        return None
    return GuidanceOutcomeView(
        result=outcome.result,  # type: ignore[arg-type]  # CHECK result_known
        actual_value=outcome.actual_value,
        actual_source_ids=[str(s) for s in outcome.actual_source_ids],
        delta_vs_low=outcome.delta_vs_low,
        delta_vs_high=outcome.delta_vs_high,
        delta_vs_mid=outcome.delta_vs_mid,
        delta_vs_mid_pct=outcome.delta_vs_mid_pct,
        reason_code=outcome.reason_code,
        explanation=EXPLANATIONS.get(outcome.reason_code or ""),
        computed_at=outcome.computed_at,
    )


def _value(item: GuidanceItem, outcome: GuidanceOutcome | None, doc: Document) -> GuidanceValue:
    low, high = guided(item).bounds
    return GuidanceValue(
        id=item.id,
        issued_at=item.issued_at,
        low=item.low,
        high=item.high,
        point=item.point,
        midpoint=(low + high) / 2,
        derived_range=item.derived_range,
        quote=item.quote,
        source_id=item.paragraph_id or "",
        release=GuidanceRelease(document_id=doc.id, title=doc.title, url=doc.source_url),
        outcome=_outcome(outcome),
    )


def grouped(rows: Sequence[Row]) -> list[tuple[Row, list[Row]]]:
    """(headline, revisions) per period, metric and basis, in the rows' order. Rows come sorted
    by issue date within a key, so the first is the initial guidance (FR-GD-009)."""
    groups: dict[tuple[object, ...], list[Row]] = {}
    for row in rows:
        item = row[0]
        groups.setdefault(
            (item.fiscal_year, item.fiscal_period, item.metric, item.basis), []
        ).append(row)
    return [(group[0], group[1:]) for group in groups.values()]


def guidance(
    session: Session, company: Company, *, fiscal_year: int | None = None
) -> GuidanceResponse:
    rows = repo.items_with_outcomes(session, company.id, fiscal_year=fiscal_year)
    items = []
    for (item, outcome, doc), revisions in grouped(rows):
        items.append(
            GuidanceRow(
                **_value(item, outcome, doc).model_dump(),
                fiscal_year=item.fiscal_year or 0,
                fiscal_period=item.fiscal_period or "",
                period_label=period_label(item),
                metric=item.metric,
                metric_label=label(item.metric),
                basis=item.basis,  # type: ignore[arg-type]  # verified rows always have one
                unit=item.unit,  # type: ignore[arg-type]
                revisions=[_value(i, o, d) for i, o, d in revisions],
            )
        )
    return GuidanceResponse(
        ticker=company.ticker,
        fiscal_year=fiscal_year,
        fiscal_years=repo.fiscal_years(session, company.id),
        items=items,
        scope=SCOPE,
    )


def track_record(session: Session, company: Company) -> GuidanceTrackRecord:
    """Headline quarterly revenue outcomes, newest first (FR-GD-011)."""
    headlines: list[tuple[tuple[int, str], outcomes.Outcome]] = []
    quarters: list[TrackRecordQuarter] = []
    seen: set[tuple[int, str]] = set()
    for (item, outcome, _doc), _revisions in grouped(repo.items_with_outcomes(session, company.id)):
        period = (item.fiscal_year or 0, item.fiscal_period or "")
        if item.metric != "revenue" or period[1] == "FY" or outcome is None or period in seen:
            continue
        seen.add(period)
        low, high = guided(item).bounds
        headlines.append(
            (
                period,
                outcomes.Outcome(
                    outcome.result,  # type: ignore[arg-type]
                    delta_vs_mid=outcome.delta_vs_mid,
                    delta_vs_mid_pct=outcome.delta_vs_mid_pct,
                ),
            )
        )
        quarters.append(
            TrackRecordQuarter(
                period_label=period_label(item),
                low=low,
                high=high,
                actual_value=outcome.actual_value,
                result=outcome.result,  # type: ignore[arg-type]
                delta_vs_mid_pct=outcome.delta_vs_mid_pct,
                source_id=item.paragraph_id or "",
            )
        )
    record = outcomes.track_record(headlines, metric_label=label("revenue"))
    return GuidanceTrackRecord(
        ticker=company.ticker,
        metric="revenue",
        metric_label=label("revenue"),
        n_quarters=record.n_quarters,
        n_comparable=record.n_comparable,
        n_above=record.n_above,
        n_within=record.n_within,
        n_below=record.n_below,
        avg_delta_vs_mid=record.avg_delta_vs_mid,
        avg_delta_vs_mid_pct=record.avg_delta_vs_mid_pct,
        sufficient=record.sufficient,
        label=record.label,
        quarters=quarters[: outcomes.TRACK_QUARTERS],
    )
