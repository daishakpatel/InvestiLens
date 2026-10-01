"""Q4 derivation and YTD de-cumulation (DR-022).

10-Ks report only annual figures. For flow items, Q4 = FY - (Q1 + Q2 + Q3); the result is marked
`is_derived = true` with lineage to the four source facts. 10-Q cash-flow statements are
cumulative YTD, so de-cumulate before computing quarterly deltas. Balance-sheet (stock) items are
instants — the Q4 balance is the fiscal year-end balance, never derived.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.finance.selection import Selection


@dataclass(frozen=True)
class DerivedQ4:
    value: Decimal
    input_accessions: list[str]  # lineage: FY, Q1, Q2, Q3 (CIT-003)


def derive_q4(fy: Selection, q1: Selection, q2: Selection, q3: Selection) -> DerivedQ4:
    """Q4 = FY - (Q1 + Q2 + Q3) for a flow metric, with lineage to the four inputs."""
    value = fy.value - (q1.value + q2.value + q3.value)
    lineage = [s.accession_number for s in (fy, q1, q2, q3)]
    return DerivedQ4(value=value, input_accessions=lineage)


def decumulate(ytd_by_quarter: list[Decimal]) -> list[Decimal]:
    """Turn cumulative YTD values [Q1, H1, 9M, FY] into per-quarter deltas (DR-022).

    Each quarter = this YTD - previous YTD; the first quarter is already a single quarter.
    """
    deltas: list[Decimal] = []
    previous = Decimal(0)
    for cumulative in ytd_by_quarter:
        deltas.append(cumulative - previous)
        previous = cumulative
    return deltas
