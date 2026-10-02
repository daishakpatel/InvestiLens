"""retrieval_logs persistence (RAG observability, §16.5).

Every retrieval is logged with its intent, scores, latency, and the chunk IDs returned, so the
Phase 5b evaluation harness can measure retrieval quality against the golden set.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import RetrievalLog


def record_retrieval(
    session: Session,
    *,
    query: str,
    intent: str,
    top_k: int,
    scores: dict[str, Any],
    latency_ms: int,
    chunk_ids: list[str],
    request_id: str | None = None,
) -> None:
    session.add(
        RetrievalLog(
            request_id=request_id,
            query=query,
            intent=intent,
            top_k=top_k,
            scores=scores,
            latency_ms=latency_ms,
            chunk_ids=chunk_ids,
        )
    )
