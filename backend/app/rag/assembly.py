"""Context assembly within a token budget (RAG-020, §16.5).

Produces the model-ready context with:
- a token budget per intent,
- ordering: structured metrics first, then evidence by tier (Tier 1 first), then rerank score,
- every evidence item wrapped in explicit untrusted-source delimiters carrying its `source_id`
  and metadata (RAG-040).

The system/developer instruction is returned *separately* from the untrusted context block so the
two are never concatenated into one instruction string (RAG-040); Phase 3 places them in
different message roles.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.config import Settings, get_settings
from app.ingestion.documents.tokens import estimate_tokens
from app.rag.injection import UNTRUSTED_PREAMBLE, wrap_untrusted
from app.rag.types import Evidence, Intent

# Per-intent budget multipliers over the configured base (RAG-020: budget varies by intent).
_BUDGET_MULT: dict[Intent, float] = {
    Intent.FINANCIAL_METRIC: 0.3,
    Intent.DOCUMENT_SUMMARY: 1.2,
    Intent.FINANCIAL_EXPLANATION: 1.3,
    Intent.COMPARISON: 1.3,
}


@dataclass
class AssembledContext:
    system_instruction: str
    context_block: str
    included_source_ids: list[str] = field(default_factory=list)


def budget_for(intent: Intent, settings: Settings) -> int:
    return int(settings.rag_context_token_budget * _BUDGET_MULT.get(intent, 1.0))


def _period(e: Evidence) -> str:
    if e.period_end:
        return e.period_end.isoformat()
    return e.filing_date.isoformat() if e.filing_date else ""


def _render(e: Evidence) -> str:
    unchanged = f" | unchanged since {e.unchanged_since}" if e.unchanged_since else ""
    header = (
        f"[source_id={e.source_id} | {e.filing_type or 'doc'} {_period(e)} | "
        f"{e.section or 'n/a'} | tier {e.tier}{unchanged}]"
    )
    body = e.text if not e.expanded_context else f"{e.text}\n\n{e.expanded_context}"
    return f"{header}\n{wrap_untrusted(body)}"


def assemble_context(
    *,
    intent: Intent,
    evidence: list[Evidence],
    structured_blocks: list[str] | None = None,
    settings: Settings | None = None,
) -> AssembledContext:
    """Assemble the budgeted, tier-ordered, injection-wrapped context block (RAG-020)."""
    settings = settings or get_settings()
    budget = budget_for(intent, settings)

    sections: list[str] = []
    used = 0
    included: list[str] = []

    # Structured metrics first (deterministic, highest-trust; they carry their own source IDs).
    for block in structured_blocks or []:
        cost = estimate_tokens(block)
        if used + cost > budget:
            break
        sections.append(block)
        used += cost

    # Then evidence: Tier 1 before lower tiers, higher rerank first within a tier.
    ordered = sorted(evidence, key=lambda e: (e.tier, -e.scores.get("rerank", 0.0)))
    for e in ordered:
        rendered = _render(e)
        cost = estimate_tokens(rendered)
        if used + cost > budget:
            continue  # skip oversized item but keep filling with smaller ones
        sections.append(rendered)
        used += cost
        included.append(e.source_id)

    return AssembledContext(
        system_instruction=UNTRUSTED_PREAMBLE,
        context_block="\n\n".join(sections),
        included_source_ids=included,
    )
