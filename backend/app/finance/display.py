"""Readable text for a stored metric value (spec §0: raw values in storage, $M/$B at display).

Deterministic and Decimal-only, like the rest of `app/finance/`: the figure a person reads in a
chat answer is produced here from the stored value, never by a model. Rounding is to two decimals
of the displayed unit, which stays well inside the citation verifier's 1% tolerance (CIT-005).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

_SCALES = (
    (Decimal(10) ** 12, "trillion"),
    (Decimal(10) ** 9, "billion"),
    (Decimal(10) ** 6, "million"),
)
_CENT = Decimal("0.01")
# Ratios read as "3.91x", not as a percentage. Mirrors `multiple` in the frontend metric catalog.
_MULTIPLES = frozenset(
    {"current_ratio", "debt_to_equity", "pe_ratio", "ps_ratio", "ev_revenue", "ev_ebitda"}
)
# Names that do not read well once underscores become spaces.
_LABELS = {
    "ebitda": "EBITDA",
    "eps_diluted": "Diluted EPS",
    "shares_diluted_weighted": "Diluted shares",
    "yoy_growth": "Revenue growth",
    "fcf_margin": "Free cash flow margin",
    "fcf_yield": "Free cash flow yield",
    "roe": "Return on equity",
    "roa": "Return on assets",
    "roic": "Return on invested capital",
    "capex": "Capital expenditure",
    "capex_intensity": "Capital expenditure as a share of revenue",
    "sbc_pct_revenue": "Stock-based compensation as a share of revenue",
    "pe_ratio": "Price-to-earnings ratio",
    "ps_ratio": "Price-to-sales ratio",
    "ev_revenue": "Enterprise value to revenue",
    "ev_ebitda": "Enterprise value to EBITDA",
}


def _trim(value: Decimal) -> str:
    """Two decimals, thousands separators, no trailing zeros: 7.50 → "7.5", 999.00 → "999"."""
    text = f"{value.quantize(_CENT, rounding=ROUND_HALF_UP):,f}"
    return text.rstrip("0").rstrip(".")


def _scaled(value: Decimal) -> str:
    for size, word in _SCALES:
        if abs(value) >= size:
            return f"{_trim(value / size)} {word}"
    return _trim(value)


def format_metric_value(value: Decimal | None, unit: str | None, *, metric: str = "") -> str:
    """`215938000000` USD → "$215.94 billion"; `0.7107` ratio → "71.07%"; none → "not available"."""
    if value is None:
        return "not available"  # DR-041/042: never shown as zero
    sign = "-" if value < 0 else ""
    if unit == "USD":
        return f"{sign}${_scaled(abs(value))}"
    if unit == "USD/shares":
        return f"{sign}${abs(value).quantize(_CENT, rounding=ROUND_HALF_UP):,f} per share"
    if unit == "ratio":
        return f"{_trim(value)}x" if metric in _MULTIPLES else f"{_trim(value * 100)}%"
    if unit == "shares":
        return f"{_scaled(value)} shares"
    return f"{_trim(value)} {unit or ''}".strip()


def metric_label(name: str) -> str:
    return _LABELS.get(name) or name.replace("_", " ").capitalize()


def describe_metric(name: str, period: str, value: Decimal | None, unit: str | None) -> str:
    """One sentence for a metric: "Revenue for FY2026 was $215.94 billion"."""
    shown = format_metric_value(value, unit, metric=name)
    return f"{metric_label(name)} for {period.replace('-', ' ')} was {shown}"
