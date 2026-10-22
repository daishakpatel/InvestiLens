"""Alert evaluation + dispatch (§26.2, Phase 5d; registry + watermark since Phase 7a, ADR-0039).

For each enabled alert of an active user, ask its event type's detector for events with
`watermark_at < occurred_at <= run_started_at`, deliver one notification per event (or one digest
when there are many), then move the watermark to `run_started_at`. The run's *start* is used, not
the time it finished, so an event that lands mid-run is picked up next time instead of lost.

Delivery is idempotent on its own, independent of the watermark: `notifications(alert_id,
event_key)` is unique and inserts are `ON CONFLICT DO NOTHING`, so two overlapping runs, or a run
whose watermark update failed, never deliver the same event twice (FR-AL-007/008). Each alert runs
in its own savepoint: one failing detector is logged and counted, and the others still run
(FR-AL-013).
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.alerts import registry
from app.alerts.registry import AlertEventType, DetectedEvent
from app.config import Settings, get_settings
from app.models import Alert, Company, User
from app.notifications.sender import NotificationSender
from app.observability.metrics import ALERT_DISPATCH_ERRORS, ALERT_DISPATCH_LATENCY, ALERTS_FIRED
from app.repositories import notifications as notif_repo
from app.utils.logging import get_logger, log_event

logger = get_logger(__name__)


def _digest(
    session: Session, event_type: AlertEventType, events: list[DetectedEvent]
) -> DetectedEvent:
    """Collapse a large batch into one notification that still names every event (FR-AL-015).
    Its key hashes the batch, so a re-run that detects the same batch is swallowed too."""
    keys = sorted(event.event_key for event in events)
    company_ids = {event.company_id for event in events}
    tickers = sorted(session.scalars(select(Company.ticker).where(Company.id.in_(company_ids))))
    shown = [event.title for event in events[:5]]
    more = len(events) - len(shown)
    return DetectedEvent(
        event_key="digest:" + hashlib.sha256("\n".join(keys).encode()).hexdigest()[:40],
        occurred_at=min(event.occurred_at for event in events),
        company_id=events[0].company_id,
        title=f"{len(events)} {event_type.label.lower()} alerts for {', '.join(tickers)}",
        body="; ".join(shown) + (f"; and {more} more." if more else "."),
        source_ids=tuple(dict.fromkeys(sid for event in events for sid in event.source_ids)),
        severity=max(
            (event.severity for event in events), key=("info", "warning", "critical").index
        ),
    )


def _deliver(
    session: Session,
    alert: Alert,
    user: User,
    event_type: AlertEventType,
    *,
    run_started_at: datetime,
    sender: NotificationSender,
    settings: Settings,
) -> int:
    events = event_type.detector(session, alert, alert.watermark_at, run_started_at)
    delivered = notif_repo.delivered_event_keys(
        session, alert_id=alert.id, since=alert.watermark_at
    )
    events = [event for event in events if event.event_key not in delivered]
    if not events:
        return 0
    batch = (
        [(_digest(session, event_type, events), events)]
        if len(events) > settings.alert_digest_threshold
        else [(event, [event]) for event in events]
    )
    created = 0
    for event, covered in batch:
        companies = {e.company_id for e in covered}
        sent = sender.send(
            session,
            user=user,
            alert_id=alert.id,
            # A digest across several watchlist companies belongs to none of them.
            company_id=event.company_id if len(companies) == 1 else None,
            event_key=event.event_key,
            title=event.title,
            body=event.body,
            channels=alert.channels,
            payload={
                "event_type": event_type.key,
                "severity": event.severity,
                "source_ids": list(event.source_ids),
                "event_keys": [e.event_key for e in covered],
            },
        )
        if not sent:
            continue
        created += 1
        ALERT_DISPATCH_LATENCY.observe((datetime.now(UTC) - event.occurred_at).total_seconds())
        for channel in alert.channels:
            ALERTS_FIRED.labels(event_type=event_type.key, channel=channel).inc()
    return created


def _advance_watermark(session: Session, alert: Alert, run_started_at: datetime) -> None:
    alert.watermark_at = run_started_at
    session.flush()


def check_and_dispatch(
    session: Session,
    *,
    sender: NotificationSender | None = None,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> int:
    """Evaluate every enabled alert; returns the number of notifications created."""
    settings = settings or get_settings()
    sender = sender or NotificationSender()
    run_started_at = now or datetime.now(UTC)
    created = 0
    rows = session.execute(
        select(Alert, User)
        .join(User, User.id == Alert.user_id)
        .where(Alert.enabled.is_(True), User.is_active.is_(True))
        .order_by(Alert.id)
    ).all()
    for alert, user in rows:
        alert_id, key = alert.id, alert.event_type
        event_type = registry.get(key)
        if event_type is None:  # a type removed from the registry: skip, never crash (FR-AL-004)
            log_event(
                logger,
                logging.WARNING,
                "alert.unknown_event_type",
                alert_id=alert_id,
                event_type=key,
            )
            continue
        try:
            with session.begin_nested():
                created += _deliver(
                    session,
                    alert,
                    user,
                    event_type,
                    run_started_at=run_started_at,
                    sender=sender,
                    settings=settings,
                )
            # Separate step: if it fails, the notifications above stay and the next run's
            # re-detection is swallowed by the (alert_id, event_key) constraint (FR-AL-008).
            with session.begin_nested():
                _advance_watermark(session, alert, run_started_at)
        except Exception as exc:  # one bad alert must not stop the run
            ALERT_DISPATCH_ERRORS.labels(event_type=key).inc()
            log_event(
                logger,
                logging.ERROR,
                "alert.dispatch_failed",
                alert_id=alert_id,
                event_type=key,
                error=type(exc).__name__,
            )
    session.flush()
    return created
