"""Zero-downtime re-embedding / model migration (Phase 2b, EMB-003, ADR-0013).

Switching embedding models must not blank the index while the new vectors compute. The job runs
in two phases:

1. ``stage_all`` — embed every chunk under the NEW model into the ``embedding_new`` staging
   column. Throughout this phase the live ``embedding`` column keeps serving reads unchanged.
2. ``swap`` — one atomic UPDATE promotes the staged vectors to ``embedding`` and stamps the new
   ``embedding_model`` / ``embedding_dim``, then clears staging.

``migrate_model`` runs both. Staging is resumable (only un-staged rows are embedded), and the swap
only touches rows that were actually staged, so a crash mid-backfill never loses data.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import get_settings
from app.providers.base import EmbeddingClient
from app.repositories import embeddings as embed_repo
from app.utils.logging import get_logger, log_event

logger = get_logger(__name__)


@dataclass
class ReembedCounts:
    staged: int = 0
    swapped: int = 0


def _embed_sync(client: EmbeddingClient, texts: list[str]) -> list[list[float]]:
    return [list(v) for v in asyncio.run(client.embed(texts, input_type="document"))]


def stage_all(session: Session, *, client: EmbeddingClient, batch_size: int | None = None) -> int:
    """Embed all un-staged chunks under `client`'s model into `embedding_new`. Returns count."""
    batch_size = batch_size or get_settings().embedding_batch_size
    staged = 0
    while True:
        batch = embed_repo.fetch_unstaged_batch(session, limit=batch_size)
        if not batch:
            break
        ids = [cid for cid, _ in batch]
        vectors = _embed_sync(client, [txt for _, txt in batch])
        staged += embed_repo.stage_embeddings(session, list(zip(ids, vectors, strict=True)))
    return staged


def swap(session: Session, *, client: EmbeddingClient) -> int:
    """Atomically promote staged vectors to live under `client`'s model/dim. Returns count."""
    return embed_repo.swap_staged_embeddings(session, model=client.model_name, dim=client.dimension)


def migrate_model(
    session: Session, *, client: EmbeddingClient, batch_size: int | None = None
) -> ReembedCounts:
    """Full migration: stage every chunk under the new model, then swap atomically (EMB-003)."""
    staged = stage_all(session, client=client, batch_size=batch_size)
    swapped = swap(session, client=client)
    log_event(
        logger,
        logging.INFO,
        "embed.migrate",
        model=client.model_name,
        staged=staged,
        swapped=swapped,
    )
    return ReembedCounts(staged=staged, swapped=swapped)
