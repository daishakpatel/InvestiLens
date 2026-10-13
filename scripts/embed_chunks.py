"""Generate embeddings for every un-embedded document chunk (Phase 2b).

Fills `document_chunks.embedding` for the active model (mock = deterministic offline vectors;
EMBEDDING_PROVIDER=gemini needs GEMINI_API_KEY; live Voyage needs VOYAGE_API_KEY). Run document
parsing first. Each batch is committed on its own, so the run can be stopped or hit a provider
quota and be started again where it left off. On Gemini's free tier (100 texts a minute) run it
with EMBEDDING_BATCH_SIZE=80 EMBEDDING_RATE_LIMIT_PER_SEC=0.016, which leaves room for questions
asked in the app meanwhile. A refused batch waits a minute and tries again.
Usage:  cd backend && uv run python ../scripts/embed_chunks.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db import session_scope
from app.embeddings.pipeline import EmbedCounts, embed_pending
from app.providers import get_embedding_client
from app.utils.http import HttpClientError

_MAX_REFUSALS = 5  # in a row; a daily quota will not clear by waiting
_WAIT_S = 65


def main() -> None:
    total = EmbedCounts()
    client = get_embedding_client()  # one client for the run, so its rate limiter paces every batch
    refusals = 0
    while True:
        try:
            with session_scope() as session:
                counts = embed_pending(session, client=client, max_batches=1)
        except HttpClientError:
            refusals += 1
            if refusals > _MAX_REFUSALS:
                raise
            print(f"provider refused the batch ({refusals}/{_MAX_REFUSALS}); waiting {_WAIT_S}s")
            time.sleep(_WAIT_S)
            continue
        refusals = 0
        if not counts.embedded:
            break
        total.embedded += counts.embedded
        total.batches += counts.batches
        total.tokens += counts.tokens
        total.cost_usd += counts.cost_usd
        print(
            f"embedded={total.embedded} batches={total.batches} tokens={total.tokens}", flush=True
        )
    print(
        f"embedded={total.embedded} batches={total.batches} "
        f"tokens={total.tokens} cost_usd={total.cost_usd}"
    )


if __name__ == "__main__":
    main()
