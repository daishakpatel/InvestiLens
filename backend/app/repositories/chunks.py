"""document_chunks persistence (Phase 2a). Idempotent by (document_id, parser_version)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import DocumentChunk


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
