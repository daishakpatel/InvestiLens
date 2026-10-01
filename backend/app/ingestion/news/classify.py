"""News categorization and publisher credibility tier (Phase 1e, spec §10.8, §15).

Rule-based classifier into the fixed taxonomy — a labeling task, not a factual-claim task, so it
needs no citation-verification machinery (that's Phase 3a). Deterministic and offline.
"""

from __future__ import annotations

# Fixed taxonomy (spec §10.8). `Industry` is the default when nothing else matches.
CATEGORIES = [
    "Earnings",
    "Product",
    "Regulation",
    "Legal",
    "Management",
    "Partnerships",
    "M&A",
    "Industry",
    "Macro",
]
DEFAULT_CATEGORY = "Industry"

# Keyword -> category, checked in priority order (first match wins).
_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("Earnings", ("earnings", "revenue", "profit", "guidance", "quarterly", "eps", "results")),
    ("M&A", ("acquire", "acquisition", "merger", "takeover", "buyout", "to buy")),
    ("Partnerships", ("partnership", "partner", "collaborat", "deal with", "alliance")),
    ("Regulation", ("regulat", "antitrust", "sec ", "ftc", "probe", "investigation")),
    ("Legal", ("lawsuit", "sues", "sued", "court", "settlement", "patent")),
    ("Management", ("ceo", "cfo", "executive", "resign", "appoint", "board")),
    ("Product", ("launch", "unveil", "product", "chip", "release", "roadmap")),
    ("Macro", ("inflation", "fed ", "interest rate", "tariff", "economy", "gdp")),
]

# Reputable/licensed financial outlets -> Tier 4; everything else Tier 5 (§15).
_TIER4_PUBLISHERS = {
    "reuters",
    "bloomberg",
    "wall street journal",
    "wsj",
    "dow jones",
    "cnbc",
    "financial times",
    "ft",
    "barron's",
    "barrons",
    "marketwatch",
    "associated press",
    "ap",
    "the new york times",
    "forbes",
}


def categorize(title: str, summary: str = "", provider_category: str | None = None) -> str:
    """Return a category from the fixed taxonomy (spec §10.8)."""
    text = f"{title} {summary}".lower()
    for category, keywords in _RULES:
        if any(keyword in text for keyword in keywords):
            return category
    if provider_category:
        for category in CATEGORIES:
            if provider_category.strip().lower() == category.lower():
                return category
    return DEFAULT_CATEGORY


def publisher_tier(publisher: str) -> int:
    """Source credibility tier (§15): 4 for reputable financial news, 5 otherwise."""
    return 4 if publisher.strip().lower() in _TIER4_PUBLISHERS else 5
