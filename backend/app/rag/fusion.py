"""Reciprocal Rank Fusion of ranked result lists (RAG-011).

`score(d) = Σ_i 1 / (k + rank_i(d))` over each input list, with `k ≈ 60`. RRF needs only ranks,
not comparable raw scores, so it fuses cosine similarity and `ts_rank_cd` cleanly. Pure function:
takes lists of ids (best-first) and returns fused ids with their RRF scores, descending.
"""

from __future__ import annotations

from collections.abc import Sequence


def reciprocal_rank_fusion(
    ranked_lists: Sequence[Sequence[int]], *, k: int = 60
) -> list[tuple[int, float]]:
    """Fuse ranked id lists via RRF. Returns (id, score) pairs sorted by score descending."""
    scores: dict[int, float] = {}
    for ranked in ranked_lists:
        for rank, doc_id in enumerate(ranked):  # rank 0 = best
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
