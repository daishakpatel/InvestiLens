"""Trailing-twelve-month figures (Phase 7b, FR-QT-008 … FR-QT-011, DR-QT-002/003, ADR-0040).

Pure. A flow's TTM is the sum of the four consecutive fiscal quarters ending at `as_of`, and
exists only when all four do: three quarters are never annualized into a TTM (DR-QT-002). A
balance's TTM is simply the balance at `as_of`. TTM ratios are computed by the caller from TTM
numerators and denominators, never by averaging quarterly ratios (DR-QT-003).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.finance import metrics
from app.finance.concept_map import MetricKind
from app.finance.quarterly import FiscalQuarter, QuarterValue
from app.schemas.sources import MetricInput, MetricResult

TTM_QUARTERS = 4
SHARE_COUNT_CHANGED = "share_count_changed"
# FR-QT-009: diluted shares moving more than this across the window is flagged, not hidden.
SHARE_CHANGE_LIMIT = Decimal("0.05")


@dataclass(frozen=True)
class Cited:
    """A figure with its name and backend-issued source ID, as a TTM identity input."""

    name: str
    value: Decimal
    source_id: str | None


def window(as_of: FiscalQuarter) -> list[FiscalQuarter]:
    """The four fiscal quarters a TTM ending at `as_of` covers, oldest first."""
    return as_of.trailing(TTM_QUARTERS)


def ttm_for(
    series: Mapping[FiscalQuarter, QuarterValue], as_of: FiscalQuarter, *, kind: MetricKind
) -> MetricResult:
    """TTM of one metric at `as_of`: a four-quarter sum for a flow, the latest balance for a
    stock (cash, debt, equity). Missing input -> value None with MISSING_INPUT (DR-041)."""
    if kind == "stock":
        latest = series.get(as_of)
        inputs = [
            MetricInput(
                name=as_of.label,
                value=latest.value if latest else None,
                source_id=latest.source_id if latest else None,
            )
        ]
        return MetricResult(
            value=latest.value if latest else None,
            unit=latest.unit if latest else metrics.USD,
            inputs=inputs,
            formula_id="latest_balance",
            formula_version=metrics.FORMULA_VERSION,
            warnings=[] if latest else [metrics.MISSING_INPUT],
        )
    quarters = window(as_of)
    values = [series.get(q) for q in quarters]
    return metrics.ttm_sum(
        [v.value if v else None for v in values],
        labels=[q.label for q in quarters],
        sources={q.label: v.source_id for q, v in zip(quarters, values, strict=True) if v},
        unit=next((v.unit for v in values if v), metrics.USD),
    )


def ttm_eps(
    quarterly: Mapping[FiscalQuarter, QuarterValue],
    as_of: FiscalQuarter,
    identity: Sequence[tuple[int, Cited | None]],
    *,
    unit: str,
) -> MetricResult:
    """TTM diluted EPS (FR-QT-008).

    With quarterly EPS for all four quarters, their sum. Otherwise the year-to-date identity
    `FY_prior - YTD_prior + YTD_current`, passed in as signed terms (+1/-1); at a fiscal year
    end that collapses to the year's own EPS, passed as the single term `(+1, FY)`.
    """
    quarters = window(as_of)
    if all(q in quarterly for q in quarters):
        return ttm_for(quarterly, as_of, kind="flow").model_copy(update={"unit": unit})
    inputs = [
        MetricInput(
            name=term.name if term else "missing",
            value=term.value if term else None,
            source_id=term.source_id if term else None,
        )
        for _, term in identity
    ]
    if not identity or any(term is None for _, term in identity):
        return MetricResult(
            value=None,
            unit=unit,
            inputs=inputs,
            formula_id="ttm_eps_identity",
            formula_version=metrics.FORMULA_VERSION,
            warnings=[metrics.MISSING_INPUT],
        )
    value = sum((sign * term.value for sign, term in identity if term), Decimal(0))
    return MetricResult(
        value=value,
        unit=unit,
        inputs=inputs,
        formula_id="ttm_eps_identity",
        formula_version=metrics.FORMULA_VERSION,
    )


def identity_formula(identity: Sequence[tuple[int, Cited | None]]) -> str:
    """'TTM = FY2025 - 6M YTD FY2025 + 6M YTD FY2026' for the citation drawer."""
    parts = [
        f"{'-' if sign < 0 else '+'} {term.name}" for sign, term in identity if term is not None
    ]
    return "TTM = " + " ".join(parts).removeprefix("+ ")


def share_count_changed(shares: Sequence[Decimal | None]) -> bool:
    """Diluted shares moved more than 5% between the first and last quarter that report them."""
    present = [s for s in shares if s is not None and s > 0]
    if len(present) < 2:
        return False
    return abs(present[-1] - present[0]) / present[0] > SHARE_CHANGE_LIMIT
