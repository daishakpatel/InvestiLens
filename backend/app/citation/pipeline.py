"""Citation verification + rendering entry points (Phase 3a, §13/§14).

The layer Phase 3b (reports) and 3c (chat) call: given generated text (or structured claims) plus
the per-request evidence set, verify every claim (CIT-005), score confidence (HAL-002), render
numbered citations (CIT-006), and optionally persist the per-claim outcomes. It generates nothing.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from sqlalchemy.orm import Session

from app.citation.entailment import Entailer, get_entailer
from app.citation.evidence import EvidenceItem, index_evidence
from app.citation.extract import RawClaim, split_claims
from app.citation.render import render
from app.citation.verify import verify_claim
from app.config import Settings, get_settings
from app.repositories import claim_verifications as cv_repo
from app.schemas.citations import VerifiedClaim, VerifiedOutput


def _verify_all(
    raw_claims: Sequence[RawClaim],
    evidence: Mapping[str, EvidenceItem],
    *,
    settings: Settings,
    entailer: Entailer,
) -> list[VerifiedClaim]:
    return [verify_claim(c, evidence, settings=settings, entailer=entailer) for c in raw_claims]


def verify_text(
    text: str,
    evidence: Iterable[EvidenceItem] | Mapping[str, EvidenceItem],
    *,
    settings: Settings | None = None,
    entailer: Entailer | None = None,
) -> VerifiedOutput:
    """Verify + render LLM prose containing `[SOURCE:id]` markers against the evidence set."""
    settings = settings or get_settings()
    entailer = entailer or get_entailer(settings)
    ev = evidence if isinstance(evidence, Mapping) else index_evidence(evidence)
    claims = _verify_all(split_claims(text), ev, settings=settings, entailer=entailer)
    return render(claims, ev)


def verify_claims(
    raw_claims: Sequence[RawClaim],
    evidence: Iterable[EvidenceItem] | Mapping[str, EvidenceItem],
    *,
    settings: Settings | None = None,
    entailer: Entailer | None = None,
) -> VerifiedOutput:
    """Verify + render already-segmented claims (e.g. structured report claims from Phase 3b)."""
    settings = settings or get_settings()
    entailer = entailer or get_entailer(settings)
    ev = evidence if isinstance(evidence, Mapping) else index_evidence(evidence)
    claims = _verify_all(raw_claims, ev, settings=settings, entailer=entailer)
    return render(claims, ev)


def persist(
    session: Session,
    output: VerifiedOutput,
    *,
    report_id: int | None = None,
    chat_message_id: int | None = None,
) -> int:
    """Log every claim (accepted/softened/rejected) to `claim_verifications` (CIT-005 L6)."""
    return cv_repo.record_verifications(
        session, output.claims, report_id=report_id, chat_message_id=chat_message_id
    )
