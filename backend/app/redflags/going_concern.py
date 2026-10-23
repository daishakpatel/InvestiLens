"""Going-concern sentences, with the guards that keep a disclaimer from becoming a flag
(Phase 7e, FR-RF-003, ADR-0043).

Companies often write the phrase to say there is *no* doubt, or to describe how they evaluate it,
or as a risk factor ("if we cannot raise capital, there could be substantial doubt"). Each sentence
is classified once, in this order:

1. no core match ("substantial doubt … going concern")   -> None
2. negation ("no substantial doubt", "did not raise …")  -> None
3. policy description ("evaluates whether … substantial doubt") -> None
4. hypothetical / risk-factor language                   -> GOING_CONCERN_RISK_LANGUAGE
5. alleviated by management's plans                      -> GOING_CONCERN_ALLEVIATED
6. otherwise                                             -> GOING_CONCERN
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.redflags import patterns as p

GOING_CONCERN = "going_concern"
GOING_CONCERN_ALLEVIATED = "going_concern_alleviated"
GOING_CONCERN_RISK_LANGUAGE = "going_concern_risk_language"


def classify(sentence: str) -> str | None:
    """The going-concern class of one sentence, or None when it reports no doubt."""
    if not p.GOING_CONCERN.search(sentence):
        return None
    if p.GC_NEGATION.search(sentence) or p.GC_POLICY.search(sentence):
        return None
    if p.GC_HYPOTHETICAL.search(sentence):
        return GOING_CONCERN_RISK_LANGUAGE
    if p.GC_ALLEVIATED.search(sentence):
        return GOING_CONCERN_ALLEVIATED
    return GOING_CONCERN


@dataclass(frozen=True)
class Finding:
    classification: str
    paragraph_id: str | None
    sentence: str  # quoted exactly, so the UI shows the filing's own words


def find(paragraphs: Iterable[tuple[str | None, str]]) -> dict[str, Finding]:
    """The first sentence of each class across (paragraph_id, text) pairs, in document order."""
    found: dict[str, Finding] = {}
    for paragraph_id, text in paragraphs:
        for sentence in p.sentences(text):
            kind = classify(sentence)
            if kind is not None and kind not in found:
                found[kind] = Finding(kind, paragraph_id, sentence)
    return found
