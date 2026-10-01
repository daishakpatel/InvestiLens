"""Token estimation for chunk sizing (Phase 2a).

An approximation (~4 chars/token) is deliberate: the real tokenizer is the embedding provider's
(Voyage), which we don't call during chunking. Chunk-size targets (CH-001) only need to be
roughly right, and this keeps chunking pure and offline.
"""

from __future__ import annotations

_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    return max(1, round(len(text) / _CHARS_PER_TOKEN))
