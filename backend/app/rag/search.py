"""Single-index search primitives (Phase 2b, RAG-010).

This module exposes the two retrieval indexes *individually* — semantic (pgvector/HNSW cosine)
and keyword (PostgreSQL full-text / GIN) — so each can be verified on its own. Fusion, reranking,
query rewriting, and orchestration are Phase 2c and deliberately not here.

- Semantic search sets `hnsw.ef_search` per query (EMB-004): higher = better recall, slower.
- Keyword search uses `websearch_to_tsquery('english', …)` so stemming/synonyms let exact
  financial terms ("gross margin", "restricted cash") match differently-phrased queries.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import Float, func, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import DocumentChunk
from app.providers import get_embedding_client
from app.providers.base import EmbeddingClient


@dataclass
class SearchHit:
    chunk_id: int
    score: float  # cosine similarity (vector) or ts_rank_cd (keyword); non-financial, float is fine
    text: str
    section: str | None


def _query_vector(query: str, client: EmbeddingClient | None) -> list[float]:
    client = client or get_embedding_client()
    vectors = asyncio.run(client.embed([query], input_type="query"))  # RAG-010: query input type
    return [float(x) for x in vectors[0]]


def vector_search(
    session: Session,
    *,
    query: str,
    company_id: int,
    limit: int = 40,
    client: EmbeddingClient | None = None,
    ef_search: int | None = None,
) -> list[SearchHit]:
    """Semantic (cosine) search over the HNSW index, company-scoped (RAG-013)."""
    vector = _query_vector(query, client)
    return vector_search_by_vector(
        session, vector=vector, company_id=company_id, limit=limit, ef_search=ef_search
    )


def vector_search_by_vector(
    session: Session,
    *,
    vector: Sequence[float],
    company_id: int,
    limit: int = 40,
    ef_search: int | None = None,
) -> list[SearchHit]:
    """Cosine search for a pre-computed query vector (lets tests pin exact vectors offline)."""
    ef = int(ef_search or get_settings().hnsw_ef_search)  # int() guards the inlined literal
    # ef_search tunes HNSW recall at query time (EMB-004); LOCAL = scoped to this transaction.
    # SET takes no bind params, so the value is inlined — safe because it is a validated int.
    session.execute(text(f"SET LOCAL hnsw.ef_search = {ef}"))
    distance = DocumentChunk.embedding.cosine_distance(list(vector))
    rows = session.execute(
        select(
            DocumentChunk.id, distance.label("distance"), DocumentChunk.text, DocumentChunk.section
        )
        .where(DocumentChunk.company_id == company_id, DocumentChunk.embedding.is_not(None))
        .order_by(distance)
        .limit(limit)
    ).all()
    return [SearchHit(cid, 1.0 - float(dist), txt, section) for cid, dist, txt, section in rows]


def keyword_search(
    session: Session, *, query: str, company_id: int, limit: int = 40
) -> list[SearchHit]:
    """Full-text keyword search over the GIN-indexed `tsv` column, company-scoped (RAG-010)."""
    tsquery = func.websearch_to_tsquery("english", query)
    rank = func.ts_rank_cd(DocumentChunk.tsv, tsquery, type_=Float)
    rows = session.execute(
        select(DocumentChunk.id, rank.label("rank"), DocumentChunk.text, DocumentChunk.section)
        .where(DocumentChunk.company_id == company_id, DocumentChunk.tsv.op("@@")(tsquery))
        .order_by(rank.desc())
        .limit(limit)
    ).all()
    return [SearchHit(cid, float(r), txt, section) for cid, r, txt, section in rows]
