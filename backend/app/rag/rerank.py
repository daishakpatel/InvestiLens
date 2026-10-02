"""Reranking of fused candidates (RAG-012, ADR-0014).

A `Reranker` rescores the fused top-N and returns items sorted best-first with a normalized
`scores["rerank"]` in [0, 1] (so the sufficiency threshold in RAG-018 is meaningful). The default
`LexicalReranker` is deterministic and offline: stemmed query-term overlap blended with the RRF
prior, nudged by bounded tier/recency multipliers. `IdentityReranker` keeps fusion order for
latency comparisons (`rag_rerank_enabled=False`). An LLM/cross-encoder reranker can slot in behind
this ABC later (ADR-0014).
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.config import get_settings
from app.rag.types import Evidence

_WORD = re.compile(r"[a-z0-9]+")
# fmt: off
_STOP = frozenset({
    "the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "is", "are", "was", "were",
    "be", "been", "what", "how", "why", "did", "has", "have", "does", "do", "its", "it", "their",
    "our", "we", "they", "this", "that", "these", "those", "with", "as", "at", "by", "from",
})
# fmt: on


def _terms(text: str) -> set[str]:
    # Crude singular-ization so "margins"/"risks" match "margin"/"risk" (same spirit as FTS stems).
    out: set[str] = set()
    for tok in _WORD.findall(text.lower()):
        if tok in _STOP or len(tok) < 2:
            continue
        out.add(tok[:-1] if len(tok) > 3 and tok.endswith("s") else tok)
    return out


class Reranker(ABC):
    @abstractmethod
    def rerank(self, query: str, items: Sequence[Evidence]) -> list[Evidence]:
        """Return `items` sorted best-first with `scores['rerank']` populated."""


class IdentityReranker(Reranker):
    """No reordering: carry the (normalized) RRF score through as the rerank score."""

    def rerank(self, query: str, items: Sequence[Evidence]) -> list[Evidence]:
        ranked = sorted(items, key=lambda e: e.scores.get("rrf", 0.0), reverse=True)
        top = ranked[0].scores.get("rrf", 0.0) if ranked else 0.0
        for e in ranked:
            e.scores["rerank"] = (e.scores.get("rrf", 0.0) / top) if top else 0.0
        return ranked


class LexicalReranker(Reranker):
    def __init__(self, *, overlap_weight: float = 0.65) -> None:
        self._w = overlap_weight

    def rerank(self, query: str, items: Sequence[Evidence]) -> list[Evidence]:
        q = _terms(query)
        if not q or not items:
            return IdentityReranker().rerank(query, items)
        max_rrf = max((e.scores.get("rrf", 0.0) for e in items), default=0.0) or 1.0
        for e in items:
            overlap = len(q & _terms(e.text)) / len(q)
            rrf_norm = e.scores.get("rrf", 0.0) / max_rrf
            base = self._w * overlap + (1 - self._w) * rrf_norm
            tier_mult = 1.0 + (5 - (e.tier or 5)) * 0.02  # Tier 1 gets at most +8% (bounded)
            e.scores["rerank"] = max(0.0, min(1.0, base * tier_mult))
        return sorted(items, key=lambda e: e.scores["rerank"], reverse=True)


def get_reranker() -> Reranker:
    return LexicalReranker() if get_settings().rag_rerank_enabled else IdentityReranker()
