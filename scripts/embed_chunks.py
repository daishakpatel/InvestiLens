"""Generate embeddings for every un-embedded document chunk (Phase 2b).

Fills `document_chunks.embedding` for the active model (PROVIDER_MODE=mock uses deterministic
offline vectors; live uses Voyage, needs VOYAGE_API_KEY). Run document parsing first.
Usage:  cd backend && uv run python ../scripts/embed_chunks.py
"""

from __future__ import annotations

from app.db import session_scope
from app.embeddings.pipeline import embed_pending


def main() -> None:
    with session_scope() as session:
        counts = embed_pending(session)
        print(
            f"embedded={counts.embedded} batches={counts.batches} "
            f"tokens={counts.tokens} cost_usd={counts.cost_usd}"
        )


if __name__ == "__main__":
    main()
