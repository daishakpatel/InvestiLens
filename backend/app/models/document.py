"""Document registry, filings, and retrievable chunks (spec §23.1).

`documents` is the unified registry every source points at (filings, earnings releases,
transcripts, news, IR materials). `document_chunks` holds the retrievable units with the
vector + full-text indexes the RAG pipeline (Phase 2) will query.
"""

from datetime import date, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.config import get_settings
from app.models.base import Base, TimestampMixin, intpk

_EMBEDDING_DIM = get_settings().embedding_dimension


class Document(Base, TimestampMixin):
    """Any ingested source document. `content_hash` makes ingestion idempotent (NFR-014)."""

    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("company_id", "content_hash"),)

    id: Mapped[intpk]
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    # filing|earnings_release|transcript|news|ir_material
    document_type: Mapped[str] = mapped_column(String(32))
    source_tier: Mapped[int] = mapped_column(Integer)  # 1..5 source-quality hierarchy (§15)
    title: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    raw_document_location: Mapped[str | None] = mapped_column(Text)  # object-storage key
    content_hash: Mapped[str] = mapped_column(String(64))  # sha-256 hex
    parser_version: Mapped[str | None] = mapped_column(String(32))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    doc_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)


class Filing(Base, TimestampMixin):
    """An SEC filing. `accession_number` is globally unique; `amends_filing_id` links 10-K/A."""

    __tablename__ = "filings"

    id: Mapped[intpk]
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    filing_type: Mapped[str] = mapped_column(String(16))  # 10-K, 10-Q, 8-K, 10-K/A, 4, 13F-HR…
    filing_date: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    accession_number: Mapped[str] = mapped_column(String(32), unique=True)
    source_url: Mapped[str | None] = mapped_column(Text)
    primary_document_url: Mapped[str | None] = mapped_column(Text)
    raw_document_location: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    amends_filing_id: Mapped[int | None] = mapped_column(
        ForeignKey("filings.id", ondelete="SET NULL")
    )
    items: Mapped[list[str] | None] = mapped_column(ARRAY(String))  # 8-K item codes


class DocumentChunk(Base, TimestampMixin):
    """A retrievable unit of a document: text, table, or XBRL note.

    Carries the anchor fields citations resolve against (CIT-002, ADR-0004), a nullable
    `embedding` (populated in Phase 2b), and a generated `tsv` for keyword search. The HNSW
    and GIN indexes back hybrid retrieval (RAG-010, NFR-002).
    """

    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", "parser_version"),
        Index(
            "ix_document_chunks_company_id_filing_type_filing_date",
            "company_id",
            "filing_type",
            "filing_date",
        ),
        Index(
            "ix_document_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_document_chunks_tsv", "tsv", postgresql_using="gin"),
    )

    id: Mapped[intpk]
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    chunk_type: Mapped[str] = mapped_column(String(16))  # text|table|xbrl_note
    text: Mapped[str] = mapped_column(Text)
    section: Mapped[str | None] = mapped_column(String(256))
    subsection: Mapped[str | None] = mapped_column(String(256))
    section_path: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    paragraph_id: Mapped[str | None] = mapped_column(String(64))
    parent_section_id: Mapped[str | None] = mapped_column(String(64))
    page: Mapped[int | None] = mapped_column(Integer)  # PDFs only; NULL for HTML (§13.3)
    char_start: Mapped[int | None] = mapped_column(Integer)
    char_end: Mapped[int | None] = mapped_column(Integer)
    tier: Mapped[int | None] = mapped_column(Integer)
    filing_type: Mapped[str | None] = mapped_column(String(16))
    filing_date: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(_EMBEDDING_DIM))
    embedding_model: Mapped[str | None] = mapped_column(String(64))
    parser_version: Mapped[str | None] = mapped_column(String(32))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    tsv: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english', coalesce(text, ''))", persisted=True)
    )
    chunk_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)
