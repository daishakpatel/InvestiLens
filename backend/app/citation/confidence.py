"""Confidence scoring (HAL-002).

Combine source tier, source count, retrieval score, entailment, and source agreement into one
internal score, then expose only a label (`strongly_supported | supported | limited_evidence`). The
raw score is never returned to the client (it lives in `VerifiedClaim.internal_confidence`, excluded
from serialization).
"""

from __future__ import annotations

from collections.abc import Sequence

from app.citation.evidence import EvidenceItem
from app.citation.tiers import tier_score
from app.config import Settings, get_settings
from app.schemas.citations import EntailmentLabel
from app.schemas.research import EvidenceLabel

_ENTAIL_SCORE: dict[EntailmentLabel, float] = {
    "supported": 1.0,
    "partially": 0.5,
    "unsupported": 0.0,
    "not_checked": 0.0,
}


def score_claim(
    cited: Sequence[EvidenceItem], entailment: EntailmentLabel, *, settings: Settings | None = None
) -> tuple[float, EvidenceLabel]:
    """Return (internal_score in [0,1], exposed label). Deterministic (HAL-002)."""
    s = settings or get_settings()
    if not cited:
        return 0.0, "limited_evidence"

    best_tier = min(item.tier for item in cited)
    n_norm = min(len(cited), 3) / 3
    retrieval = sum(item.retrieval_score for item in cited) / len(cited)
    entail = _ENTAIL_SCORE[entailment]
    agreement = (1.0 if entailment == "supported" else 0.6) if len(cited) >= 2 else 0.5

    raw = (
        s.citation_w_tier * tier_score(best_tier)
        + s.citation_w_sources * n_norm
        + s.citation_w_retrieval * retrieval
        + s.citation_w_entailment * entail
        + s.citation_w_agreement * agreement
    )
    score = max(0.0, min(1.0, raw))
    if score >= s.citation_label_strong:
        return score, "strongly_supported"
    if score >= s.citation_label_supported:
        return score, "supported"
    return score, "limited_evidence"
