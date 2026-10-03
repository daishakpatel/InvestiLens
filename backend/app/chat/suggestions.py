"""Suggested follow-up questions (§10.14).

Deterministic, offline templates keyed to the company and the current intent — good enough for the
MVP and fully testable. A cheap-model generator can replace this later (RAG-050); the spec marks a
model call as optional here.
"""

from __future__ import annotations

from app.rag.types import Intent

_BASE = [
    "How has revenue grown over the last three years?",
    "What are the biggest risks the company discloses?",
    "What is management saying about the outlook?",
]
_BY_INTENT: dict[Intent, list[str]] = {
    Intent.FINANCIAL_METRIC: ["How did that change year over year?", "What drove that number?"],
    Intent.RISK_ANALYSIS: ["Which risk is most emphasized?", "How have the risks changed?"],
    Intent.FINANCIAL_EXPLANATION: [
        "How did margins trend?",
        "What does management attribute it to?",
    ],
}


def suggest(company: str, intent: Intent, *, limit: int = 3) -> list[str]:
    """Return up to `limit` follow-up questions for `company`, biased by the last intent."""
    seen: set[str] = set()
    ordered = [*_BY_INTENT.get(intent, []), *_BASE]
    out: list[str] = []
    for q in ordered:
        if q not in seen:
            seen.add(q)
            out.append(q)
    return out[:limit]
