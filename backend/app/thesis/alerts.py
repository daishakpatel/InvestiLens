"""The `thesis_trigger` alert event type (Phase 7k, FR-TH-009, ADR-0049).

Fires on a KPI transition of the alert owner's own theses: into `broken`, and into `met` too if
the user asks (`notify_on`). The key is `thesis_kpi:{kpi_id}:{state}:{period_end}`, so a value
flapping inside one period notifies once per state. The body quotes only the user's own label and
threshold and the cited value, never a judgement of the thesis.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.alerts.registry import AlertEventType, DetectedEvent, register
from app.models import Alert
from app.repositories import theses as repo
from app.thesis.evaluator import SYMBOLS
from app.thesis.registry import BY_KEY, shown

State = Literal["broken", "met"]


class ThesisTriggerParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    notify_on: list[State] = Field(
        default=["broken"],
        title="Notify on",
        description="broken, and met too if wanted.",
    )


def trigger_event(
    *,
    kpi_id: int,
    company_id: int,
    ticker: str,
    label: str,
    metric: str,
    comparator: str,
    threshold: Decimal,
    state: str,
    value: Decimal,
    period: str,
    period_end: str | None,
    source_id: str,
    at: datetime,
) -> DetectedEvent:
    tracked = BY_KEY.get(metric)
    name = tracked.label if tracked else metric
    unit = tracked.unit if tracked else "ratio"
    body = (
        f"Your KPI '{label}' ({name} {SYMBOLS[comparator]} {shown(threshold, unit)}) is now "
        f"{state}: latest {shown(value, unit)} ({source_id})."
    )
    return DetectedEvent(
        event_key=f"thesis_kpi:{kpi_id}:{state}:{period_end or period}",
        occurred_at=at,
        company_id=company_id,
        title=f"{ticker}: KPI '{label}' is now {state}",
        body=body,
        source_ids=(source_id,),
        severity="warning" if state == "broken" else "info",
    )


def detect_thesis_triggers(
    session: Session, alert: Alert, since: datetime, until: datetime
) -> list[DetectedEvent]:
    params = ThesisTriggerParams.model_validate(alert.params)
    rows = repo.kpi_events_between(
        session,
        alert.user_id,  # only the alert owner's theses, ever (SEC-TH-001)
        kinds=[f"kpi_{s}" for s in params.notify_on],
        company_id=alert.company_id,
        after=since,
        until=until,
    )
    events: dict[str, DetectedEvent] = {}
    for event, kpi, thesis, ticker in rows:
        payload = event.payload or {}
        if not event.ref_id or "value" not in payload:
            continue
        detected = trigger_event(
            kpi_id=kpi.id,
            company_id=thesis.company_id,
            ticker=ticker,
            label=kpi.label,
            metric=kpi.metric,
            comparator=str(payload.get("comparator", kpi.comparator)),
            threshold=Decimal(str(payload.get("threshold", kpi.threshold))),
            state=event.kind.removeprefix("kpi_"),
            value=Decimal(str(payload["value"])),
            period=str(payload.get("period", "")),
            period_end=payload.get("period_end"),
            source_id=event.ref_id,
            at=event.occurred_at,
        )
        events.setdefault(detected.event_key, detected)
    return list(events.values())


register(
    AlertEventType(
        key="thesis_trigger",
        label="Thesis KPI changed",
        description="A KPI in one of your own theses moves to broken (or to met, if chosen) "
        "on new reported data. Your own label and threshold, and the cited value.",
        params_schema=ThesisTriggerParams,
        detector=detect_thesis_triggers,
        sample=trigger_event(
            kpi_id=1,
            company_id=1,
            ticker="NVDA",
            label="Gross margin holds above 70%",
            metric="gross_margin",
            comparator="gte",
            threshold=Decimal("0.70"),
            state="broken",
            value=Decimal("0.6812"),
            period="TTM-Q3-FY2027",
            period_end="2026-10-25",
            source_id="derived:NVDA:gross_margin:TTM-Q3-FY2027",
            at=datetime(2026, 11, 20, 21, 30, tzinfo=UTC),
        ),
    )
)
