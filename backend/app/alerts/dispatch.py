"""Alert evaluation + dispatch (§26.2, Phase 5d) — the piece Phase 4b's alert CRUD waited on.

For each active `alerts` row, check whether a triggering event has occurred since the rule's
watermark (`last_triggered_at`, or `created_at` on first evaluation) and, if so, deliver a
notification and advance the watermark. Idempotent: re-running without a new event sends nothing,
because the watermark only moves forward when something actually fired (JOB-001).

The triggering "event time" for filings/news is the *ingestion* time (`created_at`), so the
30-minute SLA (DoD) is measured from when InvestiLens learns of the event — which is what the
EDGAR poller (≤10 min) + this dispatch (every few min) together bound.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import Alert, Company, Filing, News, PriceHistory, User
from app.notifications.sender import NotificationSender

_ALERT_FILING_TYPE = {"new_10k": "10-K", "new_10q": "10-Q", "new_8k": "8-K"}


def _new_filing(
    session: Session, *, company_id: int, filing_type: str, since: datetime
) -> Filing | None:
    return session.scalar(
        select(Filing)
        .where(
            Filing.company_id == company_id,
            Filing.filing_type == filing_type,
            Filing.created_at > since,
        )
        .order_by(Filing.created_at.desc())
    )


def _new_news(
    session: Session, *, company_id: int, category: str | None, since: datetime
) -> News | None:
    conditions = [News.company_id == company_id, News.created_at > since]
    if category:
        conditions.append(News.category == category)
    return session.scalar(select(News).where(*conditions).order_by(News.created_at.desc()))


def _price_move(
    session: Session, *, company_id: int, threshold: float, since: datetime
) -> tuple[PriceHistory, float] | None:
    """Return the latest daily bar and its fractional move if |move| ≥ threshold and the bar was
    ingested since the watermark; else None."""
    bars = list(
        session.scalars(
            select(PriceHistory)
            .where(PriceHistory.company_id == company_id)
            .order_by(PriceHistory.date.desc())
            .limit(2)
        )
    )
    if len(bars) < 2:
        return None
    latest, prev = bars[0], bars[1]
    latest_close, prev_close = latest.close, prev.close
    if latest_close is None or prev_close is None or prev_close == 0:
        return None
    # Only fire on a bar we learned about after the watermark (`ingested_at`).
    if latest.ingested_at is not None and latest.ingested_at <= since:
        return None
    move = float((latest_close - prev_close) / prev_close)
    if abs(move) >= threshold:
        return latest, move
    return None


def _evaluate_alert(
    session: Session, alert: Alert, *, settings: Settings
) -> tuple[str, str] | None:
    """Return (title, body) if the alert fires now, else None."""
    # Alert rows have no created_at; on first evaluation the watermark is the epoch, so at most the
    # single newest matching filing/news fires once (the queries return one row), then it advances.
    since = alert.last_triggered_at or datetime.min.replace(tzinfo=UTC)
    company = session.get(Company, alert.company_id)
    ticker = company.ticker if company else str(alert.company_id)

    if alert.alert_type in _ALERT_FILING_TYPE:
        filing_type = _ALERT_FILING_TYPE[alert.alert_type]
        filing = _new_filing(
            session, company_id=alert.company_id, filing_type=filing_type, since=since
        )
        if filing is not None:
            return (
                f"New {filing_type} for {ticker}",
                f"{ticker} filed a {filing_type} ({filing.accession_number}).",
            )
        return None

    if alert.alert_type == "news_category":
        category = (alert.config or {}).get("category")
        news = _new_news(session, company_id=alert.company_id, category=category, since=since)
        if news is not None:
            label = category or "news"
            return (f"New {label} news for {ticker}", news.title)
        return None

    if alert.alert_type == "price_move":
        threshold = float(
            (alert.config or {}).get("threshold", settings.alert_price_move_threshold)
        )
        hit = _price_move(session, company_id=alert.company_id, threshold=threshold, since=since)
        if hit is not None:
            _bar, move = hit
            return (
                f"{ticker} moved {move:+.1%}",
                f"{ticker} closed {move:+.1%} vs the prior session (threshold {threshold:.0%}).",
            )
        return None

    return None


def check_and_dispatch(
    session: Session,
    *,
    sender: NotificationSender | None = None,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> int:
    """Evaluate every active alert; deliver + advance the watermark on each that fires. Returns the
    number of notifications sent."""
    settings = settings or get_settings()
    sender = sender or NotificationSender()
    now = now or datetime.now(UTC)
    sent = 0
    alerts = list(session.scalars(select(Alert).where(Alert.is_active.is_(True))))
    for alert in alerts:
        fired = _evaluate_alert(session, alert, settings=settings)
        if fired is None:
            continue
        user = session.get(User, alert.user_id)
        if user is None or not user.is_active:
            continue
        title, body = fired
        sender.send(
            session,
            user=user,
            alert_id=alert.id,
            company_id=alert.company_id,
            title=title,
            body=body,
            channel=alert.channel,
        )
        alert.last_triggered_at = now
        sent += 1
    session.flush()
    return sent
