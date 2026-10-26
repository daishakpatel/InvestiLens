"""The `brief_ready` alert event type (Phase 7j, FR-EB-009, ADR-0048).

One notification per (company, fiscal period, kind): the event key leaves out the version, so a
second version (after the 10-Q) is not delivered again. A preview for an estimated report date
never notifies (FR-EB-002); the brief's own `earnings_brief:{id}` source ID links to it.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.alerts.registry import AlertEventType, DetectedEvent, NoParams, register, scope_company_ids
from app.earnings.calendar import label
from app.models import Alert
from app.repositories import earnings as repo

KIND_LABEL = {"preview": "Pre-earnings preview", "brief": "Post-earnings brief"}


def brief_event(
    *,
    brief_id: int,
    ticker: str,
    company_id: int,
    period: tuple[int, str],
    kind: str,
    at: datetime,
) -> DetectedEvent:
    name = KIND_LABEL[kind]
    return DetectedEvent(
        event_key=f"brief_ready:{ticker}:{period[0]}:{period[1]}:{kind}",
        occurred_at=at,
        company_id=company_id,
        title=f"{ticker}: {name.lower()} for {label(period)} is ready",
        body=f"The {name.lower()} for {ticker} {label(period)} is ready to read.",
        source_ids=(f"earnings_brief:{brief_id}",),
    )


def detect_briefs(
    session: Session, alert: Alert, since: datetime, until: datetime
) -> list[DetectedEvent]:
    events: dict[str, DetectedEvent] = {}
    rows = repo.created_between(
        session, scope_company_ids(session, alert), after=since, until=until
    )
    for brief, ticker in rows:  # oldest first: the first version of a key wins
        if brief.kind == "preview" and brief.report_date_estimated:
            continue
        event = brief_event(
            brief_id=brief.id,
            ticker=ticker,
            company_id=brief.company_id,
            period=(brief.fiscal_year, brief.fiscal_period),
            kind=brief.kind,
            at=brief.created_at,
        )
        events.setdefault(event.event_key, event)
    return list(events.values())


register(
    AlertEventType(
        key="brief_ready",
        label="Earnings brief ready",
        description="A pre-earnings preview (only for a confirmed report date) or a "
        "post-earnings brief is ready for a company you follow.",
        params_schema=NoParams,
        detector=detect_briefs,
        sample=brief_event(
            brief_id=1,
            ticker="NVDA",
            company_id=1,
            period=(2027, "Q3"),
            kind="brief",
            at=datetime(2026, 11, 19, 22, 0, tzinfo=UTC),
        ),
    )
)
