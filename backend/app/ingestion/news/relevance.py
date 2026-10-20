"""Entity resolution & relevance scoring (Phase 1e, spec §10.8).

Scores 0-1 how relevant an article is to the company: a headline mention is strong, a summary-
only mention is moderate, and a passing/absent mention is weak (filtered by a configurable
threshold). Rule-based and deterministic.

A mention is a whole word, never a substring ("Intel" must not match "intelligence"), and the
ticker counts only in capitals ("AMD", "NASDAQ:AMD") so short tickers don't match ordinary words.
"""

from __future__ import annotations

import re
from decimal import Decimal

_TITLE_HIT = Decimal("0.9")
_SUMMARY_HIT = Decimal("0.45")
_PASSING = Decimal("0.1")

_SUFFIXES = frozenset({"inc", "corp", "corporation", "co", "company", "ltd", "plc", "holdings"})
# Too common to name a company alone ("Advanced Micro Devices"); the first two words are used.
_GENERIC = frozenset(
    {"advanced", "american", "applied", "first", "general", "global", "international"}
    | {"national", "united", "the", "new", "bank"}
)


def _mention_patterns(company_name: str, ticker: str) -> list[re.Pattern[str]]:
    words = [w for w in re.findall(r"[a-z0-9]+", company_name.lower()) if w not in _SUFFIXES]
    # Spacing is optional so "JPMorganChase" matches "JPMorgan Chase".
    phrases = {" ".join(words[:2])} if words else set()
    if words and len(words[0]) > 2 and words[0] not in _GENERIC:
        phrases.add(words[0])  # "NVIDIA" from "NVIDIA Corporation", "Intel" from "INTEL CORP"
    patterns = [re.compile(rf"\b{re.escape(p).replace(r'\ ', r'\s*')}\b", re.I) for p in phrases]
    sym = re.escape(ticker.upper())
    # A one-letter ticker is an ordinary word ("A"), so it counts only as "(A)" or "NYSE:A".
    ticker_re = rf"[(:]{sym}\b" if len(ticker) == 1 else rf"(?<![A-Za-z0-9]){sym}(?![A-Za-z0-9])"
    patterns.append(re.compile(ticker_re))
    return patterns


def relevance_score(company_name: str, ticker: str, title: str, summary: str = "") -> Decimal:
    """Return a 0-1 relevance score for the article w.r.t. the company."""
    patterns = _mention_patterns(company_name, ticker)
    if any(p.search(title) for p in patterns):
        return _TITLE_HIT
    if any(p.search(summary) for p in patterns):
        return _SUMMARY_HIT
    return _PASSING  # named only in passing / tagged by the provider but not discussed
