"""document_chunks persistence (Phase 2a). Idempotent by (document_id, parser_version)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import DocumentChunk


def get_chunks_by_ids(session: Session, ids: list[int]) -> dict[int, DocumentChunk]:
    """Load chunks by id into an id→row map (preserves the caller's own ordering)."""
    if not ids:
        return {}
    rows = session.scalars(select(DocumentChunk).where(DocumentChunk.id.in_(ids)))
    return {row.id: row for row in rows}


def get_section_siblings(
    session: Session, *, document_id: int, parent_section_id: str, exclude_chunk_id: int
) -> list[DocumentChunk]:
    """Other chunks in the same section, in document order (parent-child expansion, RAG-015)."""
    return list(
        session.scalars(
            select(DocumentChunk)
            .where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.parent_section_id == parent_section_id,
                DocumentChunk.id != exclude_chunk_id,
            )
            .order_by(DocumentChunk.chunk_index)
        )
    )


def replace_document_chunks(
    session: Session, *, document_id: int, parser_version: str, rows: list[dict[str, Any]]
) -> int:
    """Delete this parser version's chunks for the document, then bulk-insert. Returns count.

    Chunk IDs are deterministic (DP-006), so reprocessing with the same parser version yields
    identical rows.
    """
    session.execute(
        delete(DocumentChunk).where(
            DocumentChunk.document_id == document_id,
            DocumentChunk.parser_version == parser_version,
        )
    )
    if rows:
        session.bulk_insert_mappings(DocumentChunk, rows)
    return len(rows)
