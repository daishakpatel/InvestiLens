"""Entailment layer of the citation verifier (CIT-005 L3, ADR-0015).

Decides whether a cited source supports a claim: `supported | partially | unsupported`. The default
`LexicalEntailer` is deterministic and offline — content-word overlap between claim and the
concatenated cited source text, mapped by configurable thresholds. An `LLMEntailer` can slot in
behind this ABC in Phase 3b/5b; the choice is config-driven.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from app.config import Settings, get_settings
from app.schemas.citations import EntailmentLabel

_WORD = re.compile(r"[a-z0-9]+")
# fmt: off
_STOP = frozenset({
    "the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "is", "are", "was", "were",
    "be", "been", "has", "have", "had", "its", "it", "their", "our", "we", "they", "this", "that",
    "these", "those", "with", "as", "at", "by", "from", "than", "which", "also", "about",
})
# fmt: on


def _terms(text: str) -> set[str]:
    out: set[str] = set()
    for tok in _WORD.findall(text.lower()):
        if tok in _STOP or len(tok) < 2:
            continue
        out.add(tok[:-1] if len(tok) > 3 and tok.endswith("s") else tok)
    return out


class Entailer(ABC):
    @abstractmethod
    def check(self, claim: str, source_text: str) -> EntailmentLabel:
        """Return whether `source_text` supports `claim`."""


class LexicalEntailer(Entailer):
    def __init__(self, settings: Settings | None = None) -> None:
        s = settings or get_settings()
        self._hi = s.citation_entail_supported_overlap
        self._lo = s.citation_entail_partial_overlap

    def check(self, claim: str, source_text: str) -> EntailmentLabel:
        claim_terms = _terms(claim)
        if not claim_terms:
            return "unsupported"
        overlap = len(claim_terms & _terms(source_text)) / len(claim_terms)
        if overlap >= self._hi:
            return "supported"
        if overlap >= self._lo:
            return "partially"
        return "unsupported"


def get_entailer(settings: Settings | None = None) -> Entailer:
    # Config-driven seam; the LLM/NLI verifier (ADR-0015) will be selected here in Phase 3b/5b.
    return LexicalEntailer(settings)
