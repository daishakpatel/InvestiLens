"""claim_verifications persistence (CIT-005 L6).

Every verified claim — accepted, softened, or rejected — is logged with its reason code so the
Phase 5b eval harness and audits can see exactly what was dropped and why.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.models import ClaimVerification
from app.schemas.citations import VerifiedClaim


def record_verifications(
    session: Session,
    claims: Sequence[VerifiedClaim],
    *,
    report_id: int | None = None,
    chat_message_id: int | None = None,
) -> int:
    """Persist one row per claim. Returns the number written."""
    rows = [
        ClaimVerification(
            report_id=report_id,
            chat_message_id=chat_message_id,
            claim_id=claim.claim_id,
            claim_text=claim.text,
            source_ids=list(claim.source_ids),
            status=claim.status,
            reason_code=claim.reason_code,
            entailment_label=claim.entailment_label,
            numeric_match=claim.numeric_match,
        )
        for claim in claims
    ]
    session.add_all(rows)
    return len(rows)
