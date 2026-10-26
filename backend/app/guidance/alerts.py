"""The `guidance_miss` alert event type (Phase 7i, FR-GD-013, ADR-0047).

Fires once per headline (initial) guidance outcome that lands outside the guided range, keyed
`guidance_outcome:{guidance_id}`, when the outcome is first computed or its result changes. An
outcome for guidance issued more than `FRESH_DAYS` before it was computed is history being
backfilled, not news, and does not alert. The body is the neutral template only.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.alerts.registry import AlertEventType, DetectedEvent, register, scope_company_ids
from app.finance.display import format_metric_value
from app.guidance.taxonomy import Metric, label
from app.models import Alert
from app.repositories import guidance as repo

FRESH_DAYS = 200  # a quarter's guide is issued ~3 months before its actual is reported
Outside = Literal["below_range", "above_range"]


class GuidanceMissParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metrics: list[Metric] = Field(
        default=["revenue", "eps_gaap"],
        title="Metrics",
        description="Alert on these guided metrics.",
    )
    results: list[Outside] = Field(
        default=["below_range"],
        title="Outcomes",
        description="below_range, and above_range too if wanted.",
    )


def shown_value(value: Decimal | None, unit: str | None, metric: str) -> str:
    if unit in ("ratio", "percent_of_revenue"):
        return format_metric_value(value, "ratio")
    return format_metric_value(value, "USD/shares" if metric.startswith("eps") else "USD")


def guidance_event(
    *,
    guidance_id: int,
    ticker: str,
    company_id: int,
    metric: str,
    unit: str | None,
    result: str,
    actual: Decimal | None,
    low: Decimal,
    high: Decimal,
    source_ids: tuple[str, ...],
    at: datetime,
) -> DetectedEvent:
    where = "below" if result == "below_range" else "above"
    guided = (
        shown_value(low, unit, metric)
        if low == high
        else f"{shown_value(low, unit, metric)}\u2013{shown_value(high, unit, metric)}"
    )
    body = (
        f"{label(metric)} came in {where} the guided range ({shown_value(actual, unit, metric)} vs "
        f"{guided}). Source: {source_ids[0]}."
    )
    return DetectedEvent(
        event_key=f"guidance_outcome:{guidance_id}",
        occurred_at=at,
        company_id=company_id,
        title=f"{ticker}: {label(metric)} {where} guided range",
        body=body,
        source_ids=source_ids,
        severity="info",
    )


def detect_guidance_outcomes(
    session: Session, alert: Alert, since: datetime, until: datetime
) -> list[DetectedEvent]:
    params = GuidanceMissParams.model_validate(alert.params)
    rows = repo.headline_outcomes(
        session,
        company_ids=scope_company_ids(session, alert),
        metrics=list(params.metrics),
        results=list(params.results),
        computed_after=since,
        computed_until=until,
    )
    events = []
    for item, outcome, ticker in rows:
        fresh = item.issued_at is None or item.issued_at >= outcome.computed_at - timedelta(
            days=FRESH_DAYS
        )
        low = item.point if item.point is not None else item.low
        high = item.point if item.point is not None else item.high
        if not fresh or low is None or high is None or not item.paragraph_id:
            continue
        events.append(
            guidance_event(
                guidance_id=item.id,
                ticker=ticker,
                company_id=item.company_id,
                metric=item.metric,
                unit=item.unit,
                result=outcome.result,
                actual=outcome.actual_value,
                low=low,
                high=high,
                source_ids=(item.paragraph_id, *outcome.actual_source_ids),
                at=outcome.computed_at,
            )
        )
    return events


register(
    AlertEventType(
        key="guidance_miss",
        label="Result outside guidance",
        description="A reported quarter lands outside the range the company guided to in its "
        "own earnings release (company guidance only; no analyst estimates).",
        params_schema=GuidanceMissParams,
        detector=detect_guidance_outcomes,
        sample=guidance_event(
            guidance_id=1,
            ticker="NVDA",
            company_id=1,
            metric="revenue",
            unit="usd",
            result="below_range",
            actual=Decimal("101200000000"),
            low=Decimal("105840000000"),
            high=Decimal("110160000000"),
            source_ids=("2716_0_5", "xbrl:NVDA:revenue:Q3-FY2027"),
            at=datetime(2026, 11, 20, 21, 30, tzinfo=UTC),
        ),
    )
)
