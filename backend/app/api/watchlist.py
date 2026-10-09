"""Watchlist, alerts, notifications, and feedback endpoints (spec §24.2, §26.2).

User-scoped CRUD over `watchlists`/`watchlist_items`/`alerts`; the authenticated user comes from
the `get_current_user_id` seam (ADR-0006). Alert *dispatch* — checking for new filings/price
moves/news and writing `notifications` — runs as the `send_alerts` background job (Phase 5d);
this router exposes the CRUD plus the read side of the notifications that dispatch produces.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.api.pagination import NEXT_CURSOR_HEADER, clamp_limit, decode_cursor, encode_cursor
from app.db import get_db
from app.models import Company
from app.repositories import alerts as alert_repo
from app.repositories import companies as company_repo
from app.repositories import notifications as notif_repo
from app.repositories import watchlists as watchlist_repo
from app.schemas.chat import FeedbackRequest
from app.schemas.watchlist import (
    Alert,
    AlertCreate,
    Notification,
    Watchlist,
    WatchlistCreate,
    WatchlistItem,
)

router = APIRouter(tags=["Watchlist & Alerts"])

_DB = Depends(get_db)
_USER = Depends(get_current_user_id)


@router.get("/watchlists", response_model=list[Watchlist])
async def list_watchlists(db: Session = _DB, user_id: int = _USER) -> list[Watchlist]:
    rows = watchlist_repo.list_for_user(db, user_id=user_id)
    return [
        Watchlist(
            id=str(w.id),
            name=w.name,
            items=[
                WatchlistItem(ticker=t) for t in watchlist_repo.item_tickers(db, watchlist_id=w.id)
            ],
        )
        for w in rows
    ]


@router.post("/watchlists", status_code=201, response_model=Watchlist)
async def create_watchlist(
    body: WatchlistCreate, db: Session = _DB, user_id: int = _USER
) -> Watchlist:
    row = watchlist_repo.create(db, user_id=user_id, name=body.name)
    db.commit()
    return Watchlist(id=str(row.id), name=row.name, items=[])


@router.delete("/watchlists/{watchlist_id}", status_code=204)
async def delete_watchlist(watchlist_id: int, db: Session = _DB, user_id: int = _USER) -> None:
    if not watchlist_repo.delete_for_user(db, user_id=user_id, watchlist_id=watchlist_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "watchlist not found")
    db.commit()


@router.get("/alerts", response_model=list[Alert])
async def list_alerts(db: Session = _DB, user_id: int = _USER) -> list[Alert]:
    out: list[Alert] = []
    for a in alert_repo.list_for_user(db, user_id=user_id):
        company = db.get(Company, a.company_id)
        out.append(
            Alert(
                id=str(a.id),
                ticker=company.ticker if company else "",
                alert_type=a.alert_type,  # type: ignore[arg-type]  # DB string → Literal
                channel=a.channel,  # type: ignore[arg-type]
                is_active=a.is_active,
            )
        )
    return out


@router.post("/alerts", status_code=201, response_model=Alert)
async def create_alert(body: AlertCreate, db: Session = _DB, user_id: int = _USER) -> Alert:
    company = company_repo.get_by_ticker(db, body.ticker)
    if company is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"company {body.ticker.upper()} not ingested"
        )
    row = alert_repo.create(
        db,
        user_id=user_id,
        company_id=company.id,
        alert_type=body.alert_type,
        channel=body.channel,
    )
    db.commit()
    return Alert(
        id=str(row.id),
        ticker=company.ticker,
        alert_type=body.alert_type,
        channel=body.channel,
        is_active=True,
    )


@router.delete("/alerts/{alert_id}", status_code=204)
async def delete_alert(alert_id: int, db: Session = _DB, user_id: int = _USER) -> None:
    if not alert_repo.delete_for_user(db, user_id=user_id, alert_id=alert_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "alert not found")
    db.commit()


@router.get("/notifications", response_model=list[Notification], tags=["Notifications"])
async def list_notifications(
    response: Response,
    limit: int | None = None,
    cursor: str | None = None,
    db: Session = _DB,
    user_id: int = _USER,
) -> list[Notification]:
    """The current user's in-app notifications, newest first (from the alert-dispatch job)."""
    page_size = clamp_limit(limit)
    rows = notif_repo.list_for_user(
        db, user_id=user_id, limit=page_size + 1, after_id=decode_cursor(cursor)
    )
    has_more = len(rows) > page_size
    rows = rows[:page_size]
    if has_more and rows:
        response.headers[NEXT_CURSOR_HEADER] = encode_cursor(rows[-1].id)
    return [
        Notification(
            id=str(n.id),
            title=n.title,
            body=n.body,
            channel=n.channel,  # type: ignore[arg-type]  # DB string → Literal
            company_id=str(n.company_id) if n.company_id is not None else None,
            read=n.read_at is not None,
            created_at=n.created_at.isoformat(),
        )
        for n in rows
    ]


@router.post("/notifications/{notification_id}/read", status_code=204, tags=["Notifications"])
async def mark_notification_read(
    notification_id: int, db: Session = _DB, user_id: int = _USER
) -> None:
    if not notif_repo.mark_read(db, user_id=user_id, notification_id=notification_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "notification not found")
    db.commit()


@router.post("/feedback/report", status_code=204, tags=["Feedback"])
async def report_feedback(body: FeedbackRequest) -> None:
    """Report-level feedback. Persisting it needs a report_id the v1 contract does not carry;
    stored feedback lands with the report UI (Phase 4d). Accepted as a no-op meanwhile."""
    return None
