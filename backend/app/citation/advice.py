"""Non-advice guard for generated commentary (LGL-006, §37.1/§37.2).

Company comparison and portfolio analysis produce *analysis*, never a buy/sell/hold
recommendation. The citation verifier already drops any claim that isn't supported by cited
evidence (a bare "you should buy" has no source), but this adds an explicit, deterministic
belt-and-suspenders check on the final rendered text: if recommendation language slips through, the
caller discards the commentary rather than surfacing advice.
"""

from __future__ import annotations

import re

# Recommendation / directional-advice language that must never appear in output. Kept deliberately
# broad: analyst-action verbs, personal directives, and valuation calls.
_ADVICE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(you|investors?|one|we)\s+(should|ought to|must|could)\s+(buy|sell|hold|avoid|"
        r"add|trim|accumulate|exit|rebalance|overweight|underweight)\b",
        re.I,
    ),
    re.compile(
        r"\b(buy|sell|hold|strong buy|strong sell|overweight|underweight|outperform|"
        r"underperform|market perform)\s+(rating|recommendation|call|signal)\b",
        re.I,
    ),
    re.compile(r"\b(we|i)\s+(recommend|advise|suggest you|rate)\b", re.I),
    re.compile(r"\b(is|are)\s+a\s+(buy|sell|strong buy|strong sell)\b", re.I),
    re.compile(
        r"\b(price target|fair value estimate|attractive entry|good investment|"
        r"better investment|worth buying|worth selling)\b",
        re.I,
    ),
    re.compile(
        r"\b(recommend|advise)\s+(buying|selling|holding|rebalancing|overweighting)\b", re.I
    ),
)


def advice_language(text: str) -> list[str]:
    """Return the recommendation phrases found in `text` (empty when it is clean analysis)."""
    found: list[str] = []
    for pattern in _ADVICE_PATTERNS:
        found.extend(m.group(0) for m in pattern.finditer(text))
    return found


def contains_advice(text: str) -> bool:
    """True if `text` contains any buy/sell/hold or other recommendation language (LGL-006)."""
    return bool(advice_language(text))
