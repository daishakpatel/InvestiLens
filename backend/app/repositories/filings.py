"""Document + filing persistence (idempotent by content_hash / accession_number)."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import Document, Filing


def get_or_create_document(
    session: Session,
    *,
    company_id: int,
    document_type: str,
    source_tier: int,
    content_hash: str,
    title: str | None = None,
    source_url: str | None = None,
    raw_document_location: str | None = None,
    parser_version: str | None = None,
    doc_metadata: dict[str, Any] | None = None,
) -> int:
    """Return the document id, inserting it only if (company_id, content_hash) is new."""
    stmt = (
        pg_insert(Document)
        .values(
            company_id=company_id,
            document_type=document_type,
            source_tier=source_tier,
            content_hash=content_hash,
            title=title,
            source_url=source_url,
            raw_document_location=raw_document_location,
            parser_version=parser_version,
            metadata=doc_metadata,
        )
        .on_conflict_do_nothing(index_elements=[Document.company_id, Document.content_hash])
        .returning(Document.id)
    )
    doc_id = session.execute(stmt).scalar_one_or_none()
    if doc_id is not None:
        return int(doc_id)
    existing = session.scalar(
        select(Document.id).where(
            Document.company_id == company_id, Document.content_hash == content_hash
        )
    )
    if existing is None:  # unreachable: the ON CONFLICT target guarantees the row exists
        raise RuntimeError("document upsert conflicted but no existing row found")
    return int(existing)


def filing_exists(session: Session, accession_number: str) -> bool:
    return (
        session.scalar(select(Filing.id).where(Filing.accession_number == accession_number))
        is not None
    )


def get_filing_id_for_period(
    session: Session, *, company_id: int, filing_type: str, period_end: date | None
) -> int | None:
    """Find an existing (original) filing to link an amendment to."""
    return session.scalar(
        select(Filing.id).where(
            Filing.company_id == company_id,
            Filing.filing_type == filing_type,
            Filing.period_end == period_end,
        )
    )


def insert_filing(
    session: Session,
    *,
    document_id: int,
    company_id: int,
    filing_type: str,
    filing_date: date | None,
    period_end: date | None,
    accession_number: str,
    source_url: str | None,
    primary_document_url: str | None,
    content_hash: str | None,
    raw_document_location: str | None,
    amends_filing_id: int | None,
    items: list[str] | None,
) -> int | None:
    """Insert a filing; return its id, or None if the accession already existed (idempotent)."""
    stmt = (
        pg_insert(Filing)
        .values(
            document_id=document_id,
            company_id=company_id,
            filing_type=filing_type,
            filing_date=filing_date,
            period_end=period_end,
            accession_number=accession_number,
            source_url=source_url,
            primary_document_url=primary_document_url,
            content_hash=content_hash,
            raw_document_location=raw_document_location,
            amends_filing_id=amends_filing_id,
            items=items,
        )
        .on_conflict_do_nothing(index_elements=[Filing.accession_number])
        .returning(Filing.id)
    )
    filing_id = session.execute(stmt).scalar_one_or_none()
    return int(filing_id) if filing_id is not None else None
