"""KPI evaluation: arithmetic against stored metrics, nothing else (FR-TH-004..008, ADR-0049).

For each KPI the latest value of its metric and period type (`registry.series`, the same rows
the rest of the app shows) is compared with the threshold in Decimal: `met`, `broken`, or
`no_data` when there is no value. The state and the value it rests on are stored on the KPI.

An event is appended only when the state changes because the data changed:
- The first evaluation of a KPI, and the one after the user edits its metric, period or
  threshold, is a baseline. The user just set it, so it is not news and adds no event.
- `met` → `broken` (or back) appends `kpi_broken` / `kpi_met`. Moving into `no_data` updates the
  KPI without an event.
Running the evaluator again on unchanged data therefore adds nothing.
"""

from __future__ import annotations

import operator
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from sqlalchemy.orm import Session

from app.models import Company, Thesis, ThesisEvent, ThesisKpi
from app.repositories import theses as repo
from app.thesis import registry

State = Literal["met", "broken", "no_data"]
COMPARATORS: dict[str, Callable[[Decimal, Decimal], bool]] = {
    "gte": operator.ge,
    "lte": operator.le,
    "gt": operator.gt,
    "lt": operator.lt,
}
SYMBOLS = {"gte": "≥", "lte": "≤", "gt": ">", "lt": "<"}

Series = dict[tuple[str, str], list[registry.Point]]


def state_for(value: Decimal | None, comparator: str, threshold: Decimal) -> State:
    if value is None:
        return "no_data"
    return "met" if COMPARATORS[comparator](value, threshold) else "broken"


def _latest(
    session: Session, company: Company, kpi: ThesisKpi, cache: Series
) -> registry.Point | None:
    metric = registry.BY_KEY.get(kpi.metric)
    if metric is None:
        return None
    key = (kpi.metric, kpi.period_type)
    if key not in cache:
        cache[key] = registry.series(session, company, metric, kpi.period_type)
    points = cache[key]
    return points[-1] if points else None


def evaluate_kpi(
    session: Session,
    company: Company,
    kpi: ThesisKpi,
    *,
    cache: Series | None = None,
    now: datetime | None = None,
) -> ThesisEvent | None:
    """Re-evaluate one KPI; the event appended for a transition, or None."""
    point = _latest(session, company, kpi, cache if cache is not None else {})
    state = state_for(point.value if point else None, kpi.comparator, kpi.threshold)
    baseline = kpi.evaluated_at is None
    previous = kpi.state
    now = now or datetime.now(UTC)
    kpi.state = state
    kpi.last_value = point.value if point else None
    kpi.last_source_ids = list(point.source_ids) if point else []
    kpi.last_period = point.period if point else None
    kpi.last_period_end = point.period_end if point else None
    kpi.evaluated_at = now
    if baseline or state == previous or state == "no_data" or point is None:
        return None
    event = ThesisEvent(
        thesis_id=kpi.thesis_id,
        kpi_id=kpi.id,
        kind=f"kpi_{state}",
        occurred_at=now,
        ref_type="metric",
        ref_id=point.source_ids[0] if point.source_ids else None,
        payload={
            "value": str(point.value),
            "period": point.period,
            "period_end": point.period_end.isoformat() if point.period_end else None,
            "source_ids": list(point.source_ids),
            "comparator": kpi.comparator,
            "threshold": str(kpi.threshold),
            "previous_state": previous,
        },
    )
    session.add(event)
    return event


def evaluate_theses(
    session: Session, company: Company, theses: Sequence[Thesis], *, now: datetime | None = None
) -> list[ThesisEvent]:
    """Evaluate every KPI of these theses (all on `company`); each series is read once."""
    cache: Series = {}
    events = [
        evaluate_kpi(session, company, kpi, cache=cache, now=now)
        for kpi in repo.kpis(session, [t.id for t in theses])
    ]
    session.flush()
    return [e for e in events if e is not None]
