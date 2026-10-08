"""Pure evaluation metrics (spec §18.2). No I/O — ranked ids / sets / values in, scores out.

Retrieval metrics operate on document-level keys (e.g. "nvda_10k") so they match the golden set's
`expected_sources` granularity; the runner resolves each retrieved chunk to its doc key. Scores are
floats (non-financial signals); the numeric-answer check uses Decimal (financial correctness).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from decimal import Decimal

from app.citation.extract import extract_numbers


def precision_at_k(ranked: Sequence[str], relevant: set[str], k: int) -> float:
    if k <= 0:
        return 0.0
    top = ranked[:k]
    if not top:
        return 0.0
    return sum(1 for r in top if r in relevant) / len(top)


def recall_at_k(ranked: Sequence[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 1.0  # nothing to retrieve → vacuously complete
    hit = len(set(ranked[:k]) & relevant)
    return hit / len(relevant)


def reciprocal_rank(ranked: Sequence[str], relevant: set[str]) -> float:
    """MRR contribution: 1/rank of the first relevant hit, else 0."""
    for i, doc in enumerate(ranked):
        if doc in relevant:
            return 1.0 / (i + 1)
    return 0.0


def ndcg_at_k(ranked: Sequence[str], relevant: set[str], k: int) -> float:
    """Binary-gain NDCG@k. 1.0 when the relevant docs fill the top ranks."""
    if not relevant:
        return 1.0
    dcg = sum(1.0 / math.log2(i + 2) for i, doc in enumerate(ranked[:k]) if doc in relevant)
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
    return dcg / idcg if idcg else 0.0


def numeric_answer_correct(answer_text: str, value: Decimal, rel_tolerance: Decimal) -> bool:
    """True if the answer states a number within relative tolerance of the expected value.

    Reuses the citation number extractor so scale words ($60.9 billion / 60,922 million) are
    handled the same way as in verification. Deterministic — no LLM.
    """
    bound = abs(value) * rel_tolerance
    for token in extract_numbers(answer_text):
        if token.value is not None and abs(token.value - value) <= bound:
            return True
    return False
