"""Token estimation for embedding cost logging (Phase 2b).

Reuses the chunk-sizing estimator (~4 chars/token) so cost math is consistent project-wide. This
is only a fallback for the `llm_calls` cost column when a provider does not report usage; the mock
never calls a real tokenizer, and no financial output depends on it.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.ingestion.documents.tokens import estimate_tokens


def batch_tokens(texts: Sequence[str]) -> int:
    return sum(estimate_tokens(t) for t in texts)
