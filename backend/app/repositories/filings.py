"""Document + filing persistence (idempotent by content_hash / accession_number)."""

from __future__ import annotations

from collections.abc import Collection
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk, Filing


def list_filings(
    session: Session,
    *,
    company_id: int,
    filing_type: str | None,
    limit: int,
    after_id: int | None,
) -> list[Filing]:
    """A company's filings, newest first, keyset-paginated by descending id (API-002)."""
    conditions = [Filing.company_id == company_id]
    if filing_type is not None:
        conditions.append(Filing.filing_type == filing_type)
    if after_id is not None:
        conditions.append(Filing.id < after_id)
    return list(
        session.scalars(select(Filing).where(*conditions).order_by(Filing.id.desc()).limit(limit))
    )


def get_filing(session: Session, filing_id: int) -> Filing | None:
    return session.get(Filing, filing_id)


def _parsed(parser_version: str) -> Any:
    # Only filings chunked by the current parser are comparable: units rebuilt from two parser
    # versions would differ for reasons that have nothing to do with the filing's wording.
    return (
        select(DocumentChunk.id)
        .where(
            DocumentChunk.document_id == Filing.document_id,
            DocumentChunk.parser_version == parser_version,
        )
        .exists()
    )


def get_latest_filing(
    session: Session,
    *,
    company_id: int,
    filing_type: str,
    parser_version: str,
    before: date | None = None,
) -> Filing | None:
    """The company's newest parsed filing of this type, optionally strictly before a date."""
    conditions = [
        Filing.company_id == company_id,
        Filing.filing_type == filing_type,
        _parsed(parser_version),
    ]
    if before is not None:
        conditions.append(Filing.filing_date < before)
    return session.scalar(
        select(Filing).where(*conditions).order_by(Filing.filing_date.desc(), Filing.id.desc())
    )


def get_filings_by_document_ids(session: Session, document_ids: list[int]) -> list[Filing]:
    if not document_ids:
        return []
    return list(session.scalars(select(Filing).where(Filing.document_id.in_(document_ids))))


def list_filings_by_type(session: Session, *, company_id: int, filing_type: str) -> list[Filing]:
    """All of a company's filings of one type, oldest first."""
    return list(
        session.scalars(
            select(Filing)
            .where(Filing.company_id == company_id, Filing.filing_type == filing_type)
            .order_by(Filing.filing_date, Filing.id)
        )
    )


def get_section_chunks(
    session: Session, *, document_ids: list[int], section_like: str, parser_version: str
) -> list[DocumentChunk]:
    """Chunks of one section (matched on its title) across several documents, in document order."""
    if not document_ids:
        return []
    return list(
        session.scalars(
            select(DocumentChunk)
            .where(
                DocumentChunk.document_id.in_(document_ids),
                DocumentChunk.section.ilike(section_like),
                DocumentChunk.parser_version == parser_version,
            )
            .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
        )
    )


def get_filing_sections(session: Session, *, document_id: int) -> list[DocumentChunk]:
    """Distinct section chunks for a filing's document, in document order (for the outline)."""
    return list(
        session.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
    )


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
    published_at: datetime | None = None,
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
            published_at=published_at,
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


# Documents the parse step reads: filings, late-filing notices and EX-99 press releases.
_PARSEABLE = ("filing", "late_filing_notice", "earnings_release")


def parseable_documents(
    session: Session, *, company_id: int, filing_types: Collection[str] | None = None
) -> list[tuple[Document, Filing | None]]:
    """A company's stored documents with their filing (None for an exhibit), oldest first.

    With `filing_types`, only filings of those forms (exhibits have no form and are left out).
    """
    query = (
        select(Document, Filing)
        .outerjoin(Filing, Filing.document_id == Document.id)
        .where(
            Document.company_id == company_id,
            Document.document_type.in_(_PARSEABLE),
            Document.raw_document_location.is_not(None),
        )
        .order_by(Document.id)
    )
    if filing_types is not None:
        query = query.where(Filing.filing_type.in_(list(filing_types)))
    return [(document, filing) for document, filing in session.execute(query).tuples()]


def document_types(session: Session, document_ids: list[int]) -> dict[int, str]:
    """`documents.document_type` per id, in one query (no N+1 for a filings page)."""
    if not document_ids:
        return {}
    rows = session.execute(
        select(Document.id, Document.document_type).where(Document.id.in_(document_ids))
    )
    return {doc_id: doc_type for doc_id, doc_type in rows}


def exhibit_documents(
    session: Session, *, company_id: int, parent_accession: str
) -> list[Document]:
    """The EX-99 exhibit documents stored for one filing (FR-EX-006)."""
    return list(
        session.scalars(
            select(Document).where(
                Document.company_id == company_id,
                Document.document_type == "earnings_release",
                Document.doc_metadata["parent_accession"].astext == parent_accession,
            )
        )
    )


def merge_document_metadata(session: Session, document_id: int, updates: dict[str, Any]) -> None:
    """Merge keys into `documents.metadata` (the rest is kept)."""
    document = session.get(Document, document_id)
    if document is not None:
        document.doc_metadata = {**(document.doc_metadata or {}), **updates}


def get_by_accession(session: Session, accession_number: str) -> Filing | None:
    return session.scalar(select(Filing).where(Filing.accession_number == accession_number))


def filing_exists(session: Session, accession_number: str) -> bool:
    return (
        session.scalar(select(Filing.id).where(Filing.accession_number == accession_number))
        is not None
    )


def raw_document_location(session: Session, accession_number: str) -> str | None:
    return session.scalar(
        select(Filing.raw_document_location).where(Filing.accession_number == accession_number)
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
