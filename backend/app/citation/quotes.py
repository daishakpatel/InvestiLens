"""Quote checks for AI output that must prove each claim with a verbatim quote (Phase 7f).

Used by the footnote summaries (FR-FN-007): a bullet survives only if its quote appears verbatim
in the paragraph it cites and every number in the bullet matches a number in that quote, with the
claim verifier's tolerance (CIT-005 L2). Deterministic and offline.

"Verbatim" ignores whitespace and typographic quote/dash variants: parsed filing text splits a
tagged figure onto its own line ("$\\n\\n8.0\\n\\nbillion"), which a model quoting "$8.0 billion"
reproduces exactly in every character that matters.
"""

from __future__ import annotations

from app.citation.extract import extract_numbers
from app.citation.verify import number_matches

# Curly quotes and en/em dashes read as their ASCII forms.
_TYPOGRAPHIC = str.maketrans(
    {"\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "-"}
)
_MIN_QUOTE_CHARS = 20  # without spaces; shorter "quotes" ("the Company") prove nothing


def _squash(text: str) -> str:
    return "".join(text.translate(_TYPOGRAPHIC).split())


def quote_in_text(quote: str, text: str) -> bool:
    """True if `quote` appears verbatim in `text` and is long enough to mean something."""
    squashed = _squash(quote)
    return len(squashed) >= _MIN_QUOTE_CHARS and squashed in _squash(text)


def numbers_match_quote(text: str, quote: str, *, rel_tol: float) -> bool:
    """True if every number or date in `text` matches one in `quote` (CIT-005 L2 tolerance)."""
    candidates = [t.value for t in extract_numbers(quote) if t.value is not None]
    for token in extract_numbers(text):
        if token.kind == "date":
            if _squash(token.raw) not in _squash(quote):
                return False
        elif not number_matches(token, candidates, rel_tol=rel_tol):
            return False
    return True
