"""document_chunks persistence (Phase 2a). A re-parse replaces a document's chunks (ADR-0041)."""

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


def get_chunks_by_paragraph_ids(session: Session, paragraph_ids: list[str]) -> list[DocumentChunk]:
    """Chunks addressed by their backend-issued source IDs (`paragraph_id`, CIT-001)."""
    if not paragraph_ids:
        return []
    return list(
        session.scalars(select(DocumentChunk).where(DocumentChunk.paragraph_id.in_(paragraph_ids)))
    )


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
    session: Session, *, document_id: int, rows: list[dict[str, Any]]
) -> int:
    """Replace ALL of the document's chunks (any parser version) with `rows`. Returns count.

    Chunk IDs are deterministic (DP-006), so reprocessing yields identical rows. Chunks of an
    older parser version are removed too: a stale `paragraph_id` must stop resolving rather than
    keep pointing at a superseded parse (ADR-0041). Embeddings carry over to new rows with the
    same text (`content_hash`), so re-parsing unchanged text costs no embedding spend.
    """
    previous = {
        content_hash: (embedding, model, dim)
        for content_hash, embedding, model, dim in session.execute(
            select(
                DocumentChunk.content_hash,
                DocumentChunk.embedding,
                DocumentChunk.embedding_model,
                DocumentChunk.embedding_dim,
            ).where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.embedding.is_not(None),
            )
        )
    }
    session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
    for row in rows:
        carried = previous.get(row.get("content_hash"))
        if carried is not None:
            row["embedding"], row["embedding_model"], row["embedding_dim"] = carried
    if rows:
        session.bulk_insert_mappings(DocumentChunk, rows)
    return len(rows)
