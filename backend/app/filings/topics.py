"""Management language tracking (§37.5): topic intensity and a hedging index, per filing.

Lexicon counts over MD&A text — deterministic, no model involved. Every count is returned together
with the sentences that were counted and the source ID of the chunk each came from, so a data point
is never more than a click from its evidence.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Literal

from app.filings.units import paragraphs
from app.models import DocumentChunk

TOPIC_TAXONOMY_VERSION = "topic_taxonomy_v1"
HEDGING_LEXICON_VERSION = "hedging_lexicon_v1"
MDA_SECTION_LIKE = "%management%discussion%"

# topic id -> (label, phrases). Changing a phrase list changes every count: bump the version.
TOPIC_TAXONOMY: dict[str, tuple[str, tuple[str, ...]]] = {
    "ai_demand": (
        "AI Demand",
        ("artificial intelligence", "generative ai", "accelerated computing", "ai"),
    ),
    "supply_chain": (
        "Supply Chain",
        ("supply chain", "supply constraints", "suppliers", "supplier", "lead times", "shortages"),
    ),
    "margins": ("Margins", ("gross margins", "gross margin", "operating margin", "margins")),
    "regulation": (
        "Regulation",
        ("export controls", "export control", "regulations", "regulatory", "licensing requirement"),
    ),
    "china_exposure": ("China Exposure", ("china", "chinese", "hong kong")),
    "competition": ("Competition", ("competition", "competitors", "competitive")),
    "macro": ("Macro", ("inflation", "interest rates", "macroeconomic", "recession", "tariffs")),
    "capital_returns": (
        "Capital Returns",
        ("share repurchases", "share repurchase", "repurchased", "dividends", "dividend"),
    ),
}
HEDGING_TERMS = (
    "may",
    "might",
    "could",
    "possibly",
    "uncertain",
    "uncertainty",
    "uncertainties",
    "expect",
    "expects",
    "expected",
    "anticipate",
    "anticipates",
    "believe",
    "believes",
)

_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"\w+")

Flag = Literal["first_appearance", "disappeared"]


def _pattern(phrases: Sequence[str]) -> re.Pattern[str]:
    # Longest first, so "gross margin" is one mention rather than also a bare "margin".
    ordered = sorted(phrases, key=len, reverse=True)
    return re.compile(r"\b(?:" + "|".join(re.escape(p) for p in ordered) + r")\b", re.I)


_TOPIC_PATTERNS = {topic: _pattern(phrases) for topic, (_, phrases) in TOPIC_TAXONOMY.items()}
_HEDGING_PATTERN = _pattern(HEDGING_TERMS)


@dataclass(frozen=True)
class Statement:
    source_id: str
    text: str
    mentions: int


@dataclass
class Tally:
    count: int = 0
    statements: list[Statement] = field(default_factory=list)

    def per_1k(self, word_count: int) -> float:
        return round(self.count * 1000 / word_count, 3) if word_count else 0.0


@dataclass
class PeriodLanguage:
    word_count: int
    topics: dict[str, Tally]
    hedging: Tally


def analyze(chunks: Iterable[DocumentChunk]) -> PeriodLanguage:
    """Count topic and hedging mentions in one filing's management commentary."""
    topics = {topic: Tally() for topic in TOPIC_TAXONOMY}
    hedging = Tally()
    word_count = 0
    for para in paragraphs(chunks):
        for sentence in _SENTENCE.split(para.text):
            word_count += len(_WORD.findall(sentence))
            for pattern, tally in ((_HEDGING_PATTERN, hedging), *_by_topic(topics)):
                mentions = len(pattern.findall(sentence))
                if mentions:
                    tally.count += mentions
                    tally.statements.append(Statement(para.source_id, sentence, mentions))
    return PeriodLanguage(word_count=word_count, topics=topics, hedging=hedging)


def _by_topic(topics: dict[str, Tally]) -> list[tuple[re.Pattern[str], Tally]]:
    return [(_TOPIC_PATTERNS[topic], tally) for topic, tally in topics.items()]


def flags(counts: Sequence[int]) -> list[Flag | None]:
    """Per period (oldest first): did the topic first appear here, or drop out here?"""
    out: list[Flag | None] = []
    for i, count in enumerate(counts):
        if i and count and not any(counts[:i]):
            out.append("first_appearance")
        elif i and not count and counts[i - 1]:
            out.append("disappeared")
        else:
            out.append(None)
    return out
