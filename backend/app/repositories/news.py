"""News persistence (Phase 1e). Idempotent by (company_id, content_hash)."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import ColumnElement, select
from sqlalchemy.orm import Session

from app.models import News


def list_news(
    session: Session,
    *,
    company_id: int,
    category: str | None = None,
    publisher: str | None = None,
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
    min_relevance: Decimal | None = None,
    limit: int,
    after_id: int | None = None,
) -> list[News]:
    """Filtered company news, newest first, keyset-paginated by descending id (LGL-004, §24.2)."""
    conditions: list[ColumnElement[bool]] = [News.company_id == company_id]
    if category is not None:
        conditions.append(News.category == category)
    if publisher is not None:
        conditions.append(News.publisher == publisher)
    if from_dt is not None:
        conditions.append(News.published_at >= from_dt)
    if to_dt is not None:
        conditions.append(News.published_at <= to_dt)
    if min_relevance is not None:
        conditions.append(News.relevance_score >= min_relevance)
    if after_id is not None:
        conditions.append(News.id < after_id)
    return list(
        session.scalars(select(News).where(*conditions).order_by(News.id.desc()).limit(limit))
    )


def get_recent_news(
    session: Session, *, company_id: int, since: datetime, limit: int = 20
) -> list[News]:
    """Recent news for a company, newest first (RAG-031). `since` is an aware UTC datetime."""
    return list(
        session.scalars(
            select(News)
            .where(News.company_id == company_id, News.published_at >= since)
            .order_by(News.published_at.desc())
            .limit(limit)
        )
    )


def recent_since(days: int, *, now: datetime) -> datetime:
    """UTC cutoff `days` before `now` (kept here so the SQL boundary lives with the query)."""
    return now - timedelta(days=days)


def upsert_news(
    session: Session,
    *,
    company_id: int,
    document_id: int,
    content_hash: str,
    title: str,
    description: str,
    url: str,
    publisher: str,
    published_at: datetime,
    category: str,
    relevance_score: Decimal,
    event_cluster_id: str,
) -> bool:
    """Insert a news row, or update the mutable fields if it already exists. Returns True if new.

    Full article `content` is never stored (LGL-004, ADR-0008).
    """
    existing = session.scalar(
        select(News).where(News.company_id == company_id, News.content_hash == content_hash)
    )
    if existing is None:
        session.add(
            News(
                company_id=company_id,
                document_id=document_id,
                content_hash=content_hash,
                title=title,
                description=description,
                url=url,
                publisher=publisher,
                published_at=published_at,
                category=category,
                relevance_score=relevance_score,
                event_cluster_id=event_cluster_id,
                content=None,
            )
        )
        return True
    existing.description = description
    existing.category = category
    existing.relevance_score = relevance_score
    existing.event_cluster_id = event_cluster_id
    return False
