"""Shared mappers for the API layer (spec §24.1).

Keeps freshness metadata (API-008) and the FinancialMetric → MetricResult projection (DR-040) in
one place so every data endpoint surfaces them identically. Routers stay thin.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast, get_args

from sqlalchemy.orm import Session

from app.models import DataFreshness, FinancialMetric
from app.repositories import freshness as freshness_repo
from app.schemas.common import Freshness, FreshnessStatus
from app.schemas.sources import MetricInput, MetricResult

_VALID_STATUSES = set(get_args(FreshnessStatus))


def _iso(value: datetime | None) -> str:
    return (value or datetime.now(UTC)).isoformat()


def freshness_from_row(row: DataFreshness | None, *, source: str) -> Freshness:
    """Map a data_freshness row to the API envelope; ``stale`` when absent/unknown (API-008)."""
    if row is None:
        return Freshness(as_of=_iso(None), source=source, freshness_status="stale")
    status = row.status if row.status in _VALID_STATUSES else "stale"
    return Freshness(
        as_of=_iso(row.last_success_at or row.last_attempt_at),
        source=source,
        freshness_status=cast(FreshnessStatus, status),
    )


def freshness_for(session: Session, *, company_id: int, source: str) -> Freshness:
    """Build the freshness envelope for one source, defaulting to ``stale`` when never ingested."""
    row = freshness_repo.get_freshness(session, company_id=company_id, source=source)
    return freshness_from_row(row, source=source)


def metric_to_result(row: FinancialMetric) -> MetricResult:
    """Project a canonical metric row to a MetricResult with its derivation lineage (DR-040).

    A NULL ``metric_value`` means the metric was not computable; its reason code lives in
    ``quality_flags.warnings`` and is surfaced here, never replaced with a misleading zero
    (DR-041/042).
    """
    flags = row.quality_flags or {}
    raw_inputs = flags.get("inputs", []) if isinstance(flags.get("inputs"), list) else []
    inputs = [
        MetricInput(
            name=str(i.get("name", "")),
            value=i.get("value"),
            source_id=(str(i["source_id"]) if i.get("source_id") is not None else None),
        )
        for i in raw_inputs
        if isinstance(i, dict)
    ]
    warnings = flags.get("warnings", []) if isinstance(flags.get("warnings"), list) else []
    return MetricResult(
        value=row.metric_value,
        unit=row.unit,
        inputs=inputs,
        formula_id=row.formula_id or row.metric_name,
        formula_version=(str(flags["formula_version"]) if flags.get("formula_version") else None),
        warnings=[str(w) for w in warnings],
    )
