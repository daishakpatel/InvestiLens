"""Entity resolution & relevance scoring (Phase 1e, spec §10.8).

Scores 0-1 how relevant an article is to the company: a headline mention is strong, a summary-
only mention is moderate, and a passing/absent mention is weak (filtered by a configurable
threshold). Rule-based and deterministic.
"""

from __future__ import annotations

from decimal import Decimal

_TITLE_HIT = Decimal("0.9")
_SUMMARY_HIT = Decimal("0.45")
_PASSING = Decimal("0.1")


def _company_tokens(company_name: str, ticker: str) -> list[str]:
    tokens = {ticker.lower()}
    # First word of the name (e.g. "NVIDIA" from "NVIDIA Corporation"), lowercased.
    first = company_name.split()[0].lower() if company_name else ""
    if len(first) > 2:
        tokens.add(first)
    return [t for t in tokens if t]


def relevance_score(company_name: str, ticker: str, title: str, summary: str = "") -> Decimal:
    """Return a 0-1 relevance score for the article w.r.t. the company."""
    tokens = _company_tokens(company_name, ticker)
    title_l = title.lower()
    summary_l = summary.lower()
    if any(t in title_l for t in tokens):
        return _TITLE_HIT
    if any(t in summary_l for t in tokens):
        return _SUMMARY_HIT
    return _PASSING  # named only in passing / tagged by the provider but not discussed
