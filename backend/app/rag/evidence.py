"""Evidence construction + backend-issued source IDs (ADR-0004, CIT-001/002).

Turns a `DocumentChunk` ORM row into an `Evidence` carrying a typed `SourceRecord`. The source_id
is the chunk's deterministic `paragraph_id` (DP-006), so citations stay stable across reprocessing
with the same parser version and always resolve to an exact anchor. Source IDs are issued here (the
backend), never by an LLM (CIT-001).
"""

from __future__ import annotations

from typing import Any

from app.models import DocumentChunk
from app.rag.types import Evidence
from app.schemas.sources import SourceRecord, TableChunkSource, TextChunkSource


def _meta(chunk: DocumentChunk) -> dict[str, Any]:
    return chunk.chunk_metadata or {}


def _source_for(chunk: DocumentChunk) -> SourceRecord:
    tier = chunk.tier or 1
    anchor = chunk.paragraph_id or f"{chunk.document_id}_{chunk.chunk_index}"
    section_path = list(chunk.section_path or [])
    if chunk.chunk_type == "table":
        meta = _meta(chunk)
        return TableChunkSource(
            source_id=anchor,
            tier=tier,
            document_id=str(chunk.document_id),
            table_id=str(meta.get("table_id", anchor)),
            row_labels=list(meta.get("row_labels", []) or []),
            col_labels=list(meta.get("col_labels", []) or []),
            cell_refs=list(meta.get("cell_refs", []) or []),
        )
    return TextChunkSource(
        source_id=anchor,
        tier=tier,
        document_id=str(chunk.document_id),
        section_path=section_path,
        paragraph_id=chunk.paragraph_id,
        char_start=chunk.char_start,
        char_end=chunk.char_end,
        page=chunk.page,
    )


def build_evidence(chunk: DocumentChunk, *, scores: dict[str, float]) -> Evidence:
    """Build an `Evidence` (typed source + anchor + scores) from a chunk row."""
    return Evidence(
        chunk_id=chunk.id,
        document_id=chunk.document_id,
        source=_source_for(chunk),
        text=chunk.text,
        section=chunk.section,
        tier=chunk.tier or 1,
        filing_type=chunk.filing_type,
        filing_date=chunk.filing_date,
        period_end=chunk.period_end,
        parent_section_id=chunk.parent_section_id,
        dedup_hash=str(_meta(chunk).get("dedup_hash")) if _meta(chunk).get("dedup_hash") else None,
        scores=dict(scores),
    )
