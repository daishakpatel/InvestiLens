"""Earnings calendar and brief persistence (Phase 7j, FR-EB-001/007, ADR-0048)."""

from __future__ import annotations

from collections.abc import Collection, Sequence
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import (
    Company,
    Document,
    DocumentChunk,
    EarningsBrief,
    EarningsEvent,
    Watchlist,
    WatchlistItem,
)


def upsert_events(session: Session, rows: Sequence[dict[str, Any]]) -> None:
    """One row per (company, fiscal period); a later run replaces the date and its source (an
    estimate becomes the reported date once the 8-K is filed)."""
    if not rows:
        return
    stmt = insert(EarningsEvent).values(list(rows))
    session.execute(
        stmt.on_conflict_do_update(
            constraint="uq_earnings_events_period",
            set_={
                c: stmt.excluded[c]
                for c in ("report_date", "report_time", "source", "status", "source_id", "quote")
            },
        )
    )


def events(session: Session, company_id: int) -> list[EarningsEvent]:
    """The company's events, newest period first. Reloaded from the row, since the upsert above
    bypasses the session's copies of the same events."""
    return list(
        session.scalars(
            select(EarningsEvent)
            .where(EarningsEvent.company_id == company_id)
            .order_by(EarningsEvent.fiscal_year.desc(), EarningsEvent.fiscal_period.desc())
            .execution_options(populate_existing=True)
        )
    )


def announcement_chunks(
    session: Session, company_id: int, *, after: date | None, like: str
) -> list[DocumentChunk]:
    """Text chunks of the company's 8-Ks and press releases published after `after` whose text
    matches `like` (a cheap prefilter; the strict regex runs in code)."""
    query = (
        select(DocumentChunk)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            DocumentChunk.company_id == company_id,
            DocumentChunk.text.ilike(like),
            (DocumentChunk.filing_type == "8-K") | (Document.document_type == "earnings_release"),
        )
        .order_by(DocumentChunk.filing_date.desc().nulls_last(), DocumentChunk.id)
    )
    if after is not None:
        query = query.where(DocumentChunk.filing_date > after)
    return list(session.scalars(query))


def is_covered(session: Session, company: Company, seed_tickers: Collection[str]) -> bool:
    """Briefs cost a model call, so they are made only for watched or seed companies (FR-EB-012)."""
    if company.ticker in seed_tickers:
        return True
    watched = session.scalar(
        select(WatchlistItem.id)
        .join(Watchlist, Watchlist.id == WatchlistItem.watchlist_id)
        .where(WatchlistItem.company_id == company.id)
        .limit(1)
    )
    return watched is not None


def find_brief(
    session: Session, company_id: int, period: tuple[int, str], kind: str, inputs_hash: str
) -> EarningsBrief | None:
    return session.scalar(
        select(EarningsBrief).where(
            EarningsBrief.company_id == company_id,
            EarningsBrief.fiscal_year == period[0],
            EarningsBrief.fiscal_period == period[1],
            EarningsBrief.kind == kind,
            EarningsBrief.inputs_hash == inputs_hash,
        )
    )


def latest_version(
    session: Session, company_id: int, period: tuple[int, str], kind: str
) -> EarningsBrief | None:
    return session.scalar(
        select(EarningsBrief)
        .where(
            EarningsBrief.company_id == company_id,
            EarningsBrief.fiscal_year == period[0],
            EarningsBrief.fiscal_period == period[1],
            EarningsBrief.kind == kind,
        )
        .order_by(EarningsBrief.version.desc())
        .limit(1)
    )


def add_brief(session: Session, **values: Any) -> EarningsBrief:
    brief = EarningsBrief(**values)
    session.add(brief)
    session.flush()
    return brief


def briefs(
    session: Session,
    company_id: int,
    *,
    kind: str | None = None,
    fiscal_year: int | None = None,
    fiscal_period: str | None = None,
    limit: int = 20,
) -> list[EarningsBrief]:
    conditions = [EarningsBrief.company_id == company_id]
    if kind is not None:
        conditions.append(EarningsBrief.kind == kind)
    if fiscal_year is not None:
        conditions.append(EarningsBrief.fiscal_year == fiscal_year)
    if fiscal_period is not None:
        conditions.append(EarningsBrief.fiscal_period == fiscal_period)
    return list(
        session.scalars(
            select(EarningsBrief)
            .where(*conditions)
            .order_by(
                EarningsBrief.fiscal_year.desc(),
                EarningsBrief.fiscal_period.desc(),
                EarningsBrief.kind,
                EarningsBrief.version.desc(),
            )
            .limit(limit)
        )
    )


def created_since(session: Session, since: datetime) -> int:
    """Brief versions stored since `since`, across all companies (the daily cap, FR-EB-012)."""
    return (
        session.scalar(
            select(func.count()).select_from(EarningsBrief).where(EarningsBrief.created_at >= since)
        )
        or 0
    )


def created_between(
    session: Session, company_ids: Collection[int], *, after: datetime, until: datetime
) -> list[tuple[EarningsBrief, str]]:
    """Brief versions stored in (after, until], oldest first, with the ticker (for alerts)."""
    if not company_ids:
        return []
    rows = session.execute(
        select(EarningsBrief, Company.ticker)
        .join(Company, Company.id == EarningsBrief.company_id)
        .where(
            EarningsBrief.company_id.in_(company_ids),
            EarningsBrief.created_at > after,
            EarningsBrief.created_at <= until,
        )
        .order_by(EarningsBrief.created_at, EarningsBrief.id)
    )
    return [(brief, ticker) for brief, ticker in rows]
