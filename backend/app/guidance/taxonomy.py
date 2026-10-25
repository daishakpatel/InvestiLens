"""The guidance metrics we track and how each one's actual is read (Phase 7i, FR-GD-001/007).

`guidance_metric_v1` is a fixed list: the model may only report these, and each has the units it
can be guided in. `ACTUALS` is the explicit map from a guided metric to the `financial_metrics`
rows of the same fiscal period that give its GAAP actual; a ratio is computed here from two rows
of that period, never read from another period. Extend sparingly.
"""

from __future__ import annotations

from typing import Literal

TAXONOMY_VERSION = "guidance_metric_v1"

Metric = Literal[
    "revenue",
    "gross_margin",
    "operating_margin",
    "eps_gaap",
    "eps_non_gaap",
    "operating_expenses",
    "capex",
    "tax_rate",
    "free_cash_flow",
]
Unit = Literal["usd", "ratio", "percent_of_revenue"]
Basis = Literal["gaap", "non_gaap", "unspecified"]

# metric -> (label, units it may be guided in). The first unit is the natural one.
METRICS: dict[str, tuple[str, tuple[str, ...]]] = {
    "revenue": ("Revenue", ("usd",)),
    "gross_margin": ("Gross margin", ("ratio",)),
    "operating_margin": ("Operating margin", ("ratio",)),
    "eps_gaap": ("EPS (GAAP)", ("usd",)),
    "eps_non_gaap": ("EPS (non-GAAP)", ("usd",)),
    "operating_expenses": ("Operating expenses", ("usd", "percent_of_revenue")),
    "capex": ("Capital expenditure", ("usd", "percent_of_revenue")),
    "tax_rate": ("Tax rate", ("ratio",)),
    "free_cash_flow": ("Free cash flow", ("usd",)),
}

# metric -> (a, op, b) over financial_metrics.metric_name: the actual is a, or a op b. None means
# no GAAP actual can stand in for it, so it is never compared (DR-GD-001).
ACTUALS: dict[str, tuple[str, str, str] | tuple[str] | None] = {
    "revenue": ("revenue",),
    "gross_margin": ("gross_profit", "/", "revenue"),
    "operating_margin": ("operating_income", "/", "revenue"),
    "eps_gaap": ("eps_diluted",),
    "eps_non_gaap": None,
    # Operating income = gross profit - operating expenses, as every release presents it.
    "operating_expenses": ("gross_profit", "-", "operating_income"),
    "capex": ("capex",),
    "tax_rate": ("income_tax_expense", "/", "pretax_income"),
    "free_cash_flow": ("operating_cash_flow", "-", "capex"),
}

# A figure guided without saying GAAP or non-GAAP is compared only where no non-GAAP version is
# customary; "EPS of $1.10" alone could be either, so it is not compared.
UNSPECIFIED_COMPARABLE = frozenset({"revenue", "capex"})


def label(metric: str) -> str:
    return METRICS[metric][0] if metric in METRICS else metric.replace("_", " ").capitalize()


def actual_inputs() -> set[str]:
    """Every financial_metrics name an actual can need (plus revenue, for percent_of_revenue)."""
    names = {"revenue"}
    for formula in ACTUALS.values():
        if formula is not None:
            names.update(formula[::2])
    return names
