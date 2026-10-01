"""Traceable 2-sentence news summaries (Phase 1e, spec §10.8 / FR-025).

The summary is derived from the article's own text (provider summary, else headline), so every
sentence traces back to the source — no invented facts. Phase 3a applies full verification; here
we only guarantee traceability.
"""

from __future__ import annotations

import re

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def two_sentence_summary(title: str, summary: str) -> str:
    """Return at most the first two sentences of the source text (summary, else title)."""
    source = summary.strip() or title.strip()
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(source) if s.strip()]
    if not sentences:
        return title.strip()
    return " ".join(sentences[:2])
