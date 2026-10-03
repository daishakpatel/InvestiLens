"""Watchlist persistence (spec §26.2). User-scoped; every query is filtered by `user_id`."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Company, Watchlist, WatchlistItem


def list_for_user(session: Session, *, user_id: int) -> list[Watchlist]:
    return list(
        session.scalars(
            select(Watchlist).where(Watchlist.user_id == user_id).order_by(Watchlist.id)
        )
    )


def item_tickers(session: Session, *, watchlist_id: int) -> list[str]:
    """Tickers on a watchlist, in insertion order (joins items → companies)."""
    return list(
        session.scalars(
            select(Company.ticker)
            .join(WatchlistItem, WatchlistItem.company_id == Company.id)
            .where(WatchlistItem.watchlist_id == watchlist_id)
            .order_by(WatchlistItem.id)
        )
    )


def create(session: Session, *, user_id: int, name: str) -> Watchlist:
    row = Watchlist(user_id=user_id, name=name)
    session.add(row)
    session.flush()
    return row


def add_item(session: Session, *, watchlist_id: int, company_id: int) -> None:
    session.add(
        WatchlistItem(watchlist_id=watchlist_id, company_id=company_id, added_at=datetime.now(UTC))
    )


def delete_for_user(session: Session, *, user_id: int, watchlist_id: int) -> bool:
    """Delete a watchlist the user owns; return False if it is not theirs / not found."""
    row = session.get(Watchlist, watchlist_id)
    if row is None or row.user_id != user_id:
        return False
    session.execute(delete(Watchlist).where(Watchlist.id == watchlist_id))
    return True
