"""metric_gaps persistence (FR-QT-010, ADR-0040).

Refreshed on every metrics run: a company's gaps are deleted and the new set inserted in one
statement, so the table always describes the latest build (ING-001 idempotent).
"""

from __future__ import annotations

from collections.abc import Collection, Iterable

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from app.models import MetricGap


def replace_company_gaps(
    session: Session, company_id: int, gaps: Iterable[tuple[str, str, str]]
) -> int:
    """Replace a company's gaps with `(metric, period_label, reason)` rows. Returns the count."""
    session.execute(delete(MetricGap).where(MetricGap.company_id == company_id))
    rows = [
        {"company_id": company_id, "metric": metric, "period_label": label, "reason": reason}
        for metric, label, reason in gaps
    ]
    if rows:
        session.execute(insert(MetricGap), rows)
    return len(rows)


def replace_metric_gaps(
    session: Session,
    company_id: int,
    metrics: Collection[str],
    gaps: Iterable[tuple[str, str, str]],
) -> int:
    """Replace only the gaps of `metrics` (a later builder's own, Phase 7f), keeping the rest."""
    session.execute(
        delete(MetricGap).where(MetricGap.company_id == company_id, MetricGap.metric.in_(metrics))
    )
    rows = [
        {"company_id": company_id, "metric": metric, "period_label": label, "reason": reason}
        for metric, label, reason in gaps
    ]
    if rows:
        session.execute(insert(MetricGap), rows)
    return len(rows)


def gaps_for_company(session: Session, company_id: int) -> list[MetricGap]:
    return list(
        session.scalars(
            select(MetricGap)
            .where(MetricGap.company_id == company_id)
            .order_by(MetricGap.metric, MetricGap.period_label)
        )
    )
