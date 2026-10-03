"""Citation rendering (CIT-006).

Map accepted claims' validated source IDs to sequential `[1]`, `[2]` numbers in first-appearance
order, append them to each claim, and build the reference list. Rejected claims are dropped from the
rendered text (they are still logged, CIT-005 L6). `sufficient=False` when every factual claim was
rejected (HAL-003 abstention).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.citation.evidence import EvidenceItem
from app.citation.extract import has_factual_content
from app.schemas.citations import Citation, VerifiedClaim, VerifiedOutput
from app.schemas.sources import (
    DerivedMetricSource,
    EarningsReleaseSource,
    NewsItemSource,
    SourceRecord,
    TableChunkSource,
    TextChunkSource,
    XbrlFactSource,
)

_RENDERED = {"accepted", "softened"}


def citation_text(source: SourceRecord) -> str:
    """Human-readable reference label from a source's anchor fields."""
    if isinstance(source, TextChunkSource):
        path = " > ".join(source.section_path) if source.section_path else "document"
        return f"{source.document_id} — {path}"
    if isinstance(source, TableChunkSource):
        return f"{source.document_id} — table {source.table_id}"
    if isinstance(source, XbrlFactSource):
        return f"{source.concept_tag} ({source.accession_number})"
    if isinstance(source, DerivedMetricSource):
        period = f" {source.period}" if source.period else ""
        return f"{source.formula_id}{period} (derived)"
    if isinstance(source, NewsItemSource):
        publisher = source.publisher or "news"
        return f"{publisher} — {source.news_id}"
    if isinstance(source, EarningsReleaseSource):
        return f"{source.document_id} (earnings release)"
    return source.source_id


def render(claims: Sequence[VerifiedClaim], evidence: Mapping[str, EvidenceItem]) -> VerifiedOutput:
    """Number accepted claims' sources and build the rendered text + reference list (CIT-006)."""
    numbering: dict[str, int] = {}
    rendered_parts: list[str] = []

    for claim in claims:
        if claim.status not in _RENDERED:
            continue
        numbers: list[int] = []
        for sid in claim.source_ids:
            if sid not in numbering:
                numbering[sid] = len(numbering) + 1
            numbers.append(numbering[sid])
        claim.citation_numbers = numbers
        marks = "".join(f"[{n}]" for n in numbers)
        rendered_parts.append(f"{claim.text}{marks}" if marks else claim.text)

    citations = [
        Citation(
            number=number,
            source_id=sid,
            source_type=evidence[sid].source.source_type,
            citation_text=citation_text(evidence[sid].source),
            tier=evidence[sid].tier,
            url=evidence[sid].source.url,
        )
        for sid, number in sorted(numbering.items(), key=lambda kv: kv[1])
        if sid in evidence
    ]

    factual = [c for c in claims if has_factual_content(c.text)]
    accepted_factual = [c for c in factual if c.status in _RENDERED and c.source_ids]
    sufficient = not factual or bool(accepted_factual)

    return VerifiedOutput(
        rendered_text=" ".join(rendered_parts),
        claims=list(claims),
        citations=citations,
        sufficient=sufficient,
    )
