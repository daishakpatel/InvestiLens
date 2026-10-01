"""document_chunks embedding persistence (Phase 2b, EMB-001/003).

Two write paths:
- `update_embeddings` fills the live `embedding` column (initial population / top-up).
- `stage_embeddings` + `swap_staged_embeddings` implement the zero-downtime model migration:
  a new model backfills `embedding_new` while `embedding` keeps serving reads, then one atomic
  UPDATE promotes the staged vectors (ADR-0013).
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import CursorResult, Select, bindparam, select, text, update
from sqlalchemy.orm import Session

from app.models import DocumentChunk


def _pending_query(model: str) -> Select[int, str]:
    """Chunks that still need an embedding under `model` (NULL, or a different/older model)."""
    return (
        select(DocumentChunk.id, DocumentChunk.text)
        .where(
            (DocumentChunk.embedding.is_(None)) | (DocumentChunk.embedding_model != model),
        )
        .order_by(DocumentChunk.id)
    )


def _unstaged_query() -> Select[int, str]:
    """Chunks not yet written to the staging column (resumable re-embed, EMB-003)."""
    return (
        select(DocumentChunk.id, DocumentChunk.text)
        .where(DocumentChunk.embedding_new.is_(None))
        .order_by(DocumentChunk.id)
    )


def _count(session: Session, query: Select[int, str]) -> int:
    return session.scalar(select(text("count(*)")).select_from(query.subquery())) or 0


def count_pending(session: Session, *, model: str) -> int:
    return _count(session, _pending_query(model))


def count_unstaged(session: Session) -> int:
    return _count(session, _unstaged_query())


def fetch_pending_batch(session: Session, *, model: str, limit: int) -> list[tuple[int, str]]:
    """Return up to `limit` (id, text) pairs needing embedding under `model`."""
    return [(cid, txt) for cid, txt in session.execute(_pending_query(model).limit(limit))]


def fetch_unstaged_batch(session: Session, *, limit: int) -> list[tuple[int, str]]:
    """Return up to `limit` (id, text) pairs not yet staged for re-embedding."""
    return [(cid, txt) for cid, txt in session.execute(_unstaged_query().limit(limit))]


def _bulk_set(
    session: Session,
    rows: Sequence[tuple[int, list[float]]],
    *,
    column: str,
    model: str | None,
    dim: int | None,
) -> int:
    """Bulk-UPDATE one vector column (and optionally model/dim) for the given chunk ids."""
    if not rows:
        return 0
    values: dict[str, object] = {column: bindparam("vec")}
    if model is not None:
        values["embedding_model"] = bindparam("model")
        values["embedding_dim"] = bindparam("dim")
    stmt = update(DocumentChunk).where(DocumentChunk.id == bindparam("cid")).values(**values)
    params = [
        {"cid": cid, "vec": vec, **({"model": model, "dim": dim} if model is not None else {})}
        for cid, vec in rows
    ]
    session.connection().execute(stmt, params)
    return len(rows)


def update_embeddings(
    session: Session, rows: Sequence[tuple[int, list[float]]], *, model: str, dim: int
) -> int:
    """Write vectors to the live `embedding` column with their model + dim (EMB-001)."""
    return _bulk_set(session, rows, column="embedding", model=model, dim=dim)


def stage_embeddings(session: Session, rows: Sequence[tuple[int, list[float]]]) -> int:
    """Write vectors to the staging `embedding_new` column, leaving `embedding` untouched."""
    return _bulk_set(session, rows, column="embedding_new", model=None, dim=None)


def swap_staged_embeddings(session: Session, *, model: str, dim: int) -> int:
    """Atomically promote staged vectors to live, then clear staging (EMB-003, ADR-0013).

    Only rows that were actually staged (`embedding_new IS NOT NULL`) are swapped, so a partial
    backfill never blanks a row. Returns the number of rows promoted.
    """
    result = session.execute(
        update(DocumentChunk)
        .where(DocumentChunk.embedding_new.is_not(None))
        .values(
            embedding=DocumentChunk.embedding_new,
            embedding_model=model,
            embedding_dim=dim,
            embedding_new=None,
        )
    )
    assert isinstance(result, CursorResult)  # noqa: S101  # UPDATE always yields a CursorResult
    return result.rowcount or 0
