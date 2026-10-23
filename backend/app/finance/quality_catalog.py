"""Static text for the earnings-quality dashboard (Phase 7d, FR-EQ-009). No LLM text, ever.

One entry per stored measure, in display order: a label, a one-line explanation of what the
number means, and whether it is a screening heuristic (which always carries `SCREENING_CAVEAT`,
FR-EQ-013). Wording describes signals to investigate, never conclusions (§37.7).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Measure:
    label: str
    explanation: str
    screening: bool = False


SCREENING_CAVEAT = (
    "Screening heuristic. Calibrated on US non-financial companies. Not a conclusion about this "
    "company's accounting."
)

MEASURES: dict[str, Measure] = {
    "accruals_ratio": Measure(
        "Accruals ratio",
        "(Net income - operating cash flow) / average total assets. Higher means more of "
        "earnings is not yet backed by cash.",
    ),
    "accruals_ratio_bs": Measure(
        "Balance-sheet accruals",
        "Change in net operating assets / average net operating assets. Fast growth in "
        "non-cash operating assets is worth a closer look.",
    ),
    "fcf_conversion": Measure(
        "FCF conversion",
        "Free cash flow / net income. Near or above 1 means earnings turn into cash.",
    ),
    "dso": Measure("Days sales outstanding", "Average receivables / revenue x 365."),
    "dio": Measure("Days inventory outstanding", "Average inventory / cost of revenue x 365."),
    "dpo": Measure("Days payables outstanding", "Average payables / cost of revenue x 365."),
    "cash_conversion_cycle": Measure(
        "Cash conversion cycle", "DSO + DIO - DPO: days cash is tied up in working capital."
    ),
    "dilution": Measure(
        "Share count change",
        "Change in diluted weighted shares from the prior year, adjusted for stock splits. "
        "Negative means net buybacks.",
    ),
    "beneish_m": Measure(
        "Beneish M-score",
        "Eight-ratio model (Beneish 1999). Above -1.78 flags a pattern seen in companies that "
        "later restated; a signal to investigate, not a finding.",
        screening=True,
    ),
    "altman_z": Measure(
        "Altman Z-score",
        "Financial-distress model (Altman 1968; Z'' for non-manufacturers). Zones: distress, "
        "grey, safe.",
        screening=True,
    ),
    "piotroski_f": Measure(
        "Piotroski F-score",
        "Nine pass/fail tests of profitability, funding and efficiency (Piotroski 2000). 0-9.",
        screening=True,
    ),
}

# Why a measure is not computed for a sector (DR-EQ-001): shown instead of a number.
NOT_APPLICABLE_REASONS = {
    "bank": "Not computed for banks: built for non-financial companies.",
    "reit": "Not computed for REITs.",
}
DEFAULT_NOT_APPLICABLE = "Not applicable to this company's sector."
