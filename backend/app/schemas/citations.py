"""Citation verification & rendering schemas (Phase 3a, §13/§14).

The output contract Phase 3b/3c consume: per-claim verification outcomes (CIT-005), numbered
citations with anchors (CIT-006), and a `SourceDetail` for the citation modal (GET /sources). All
confidence is exposed only as a label (HAL-002); the raw score stays backend-internal.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.research import EvidenceLabel
from app.schemas.sources import SourceRecord

VerificationStatus = Literal["accepted", "rejected", "softened"]
ReasonCode = Literal[
    "OK",
    "UNKNOWN_SOURCE",
    "NUMERIC_MISMATCH",
    "UNSUPPORTED",
    "NO_CITATION",
    "OVERREACH",
]
EntailmentLabel = Literal["supported", "partially", "unsupported", "not_checked"]


class VerifiedClaim(BaseModel):
    """One claim's verification outcome (CIT-005)."""

    claim_id: str
    text: str  # possibly softened (causal → correlation) for accepted claims
    source_ids: list[str] = []  # validated subset actually cited
    status: VerificationStatus
    reason_code: ReasonCode
    entailment_label: EntailmentLabel = "not_checked"
    numeric_match: bool | None = None
    confidence_label: EvidenceLabel | None = None  # only for accepted/softened
    internal_confidence: float | None = Field(default=None, exclude=True)  # never serialized
    citation_numbers: list[int] = []  # assigned at render for accepted claims


class Citation(BaseModel):
    """A numbered reference in first-appearance order (CIT-006)."""

    number: int
    source_id: str
    source_type: str
    citation_text: str
    tier: int
    url: str | None = None


class VerifiedOutput(BaseModel):
    """The full verified + rendered result for a block of generated text."""

    rendered_text: str
    claims: list[VerifiedClaim]
    citations: list[Citation]
    sufficient: bool = True  # False = all factual claims rejected (HAL-003 abstention)


class SourceDetail(BaseModel):
    """GET /sources/{source_id} payload: the record + marked span + deep link (CIT-006)."""

    source: SourceRecord
    text: str | None = None
    highlight_start: int | None = None
    highlight_end: int | None = None
    deep_link: str | None = None
    # For derived_metric: the "How this was calculated" inputs (CIT-003).
    lineage: list[dict[str, str]] = []
