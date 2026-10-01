"""Ingest-time validation: unit consistency (DR-024) and anomaly checks (DR-028).

Failed checks produce `data_quality_issues` records rather than silently storing a wrong number.
Anomalies are flagged, not blocked.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.finance.concept_map import UnitFamily

# Acceptable XBRL units per family.
_UNIT_FAMILY_OK: dict[UnitFamily, set[str]] = {
    "currency": {"USD"},
    "per_share": {"USD/shares"},
    "shares": {"shares"},
}


@dataclass(frozen=True)
class QualityIssue:
    issue_code: str
    metric_name: str | None
    period: str | None
    details: dict[str, object]


def check_unit(
    metric: str, unit: str, family: UnitFamily, *, period: str | None = None
) -> QualityIssue | None:
    """Flag a fact whose unit is inconsistent with its concept's expected family (DR-024)."""
    if unit not in _UNIT_FAMILY_OK[family]:
        return QualityIssue(
            issue_code="UNIT_MISMATCH",
            metric_name=metric,
            period=period,
            details={"unit": unit, "expected_family": family},
        )
    return None


def check_accounting_identity(
    assets: Decimal,
    liabilities: Decimal,
    equity: Decimal,
    *,
    period: str | None = None,
    tolerance: Decimal = Decimal("0.01"),
) -> QualityIssue | None:
    """Flag Assets != Liabilities + Equity beyond a relative tolerance (DR-028)."""
    if assets == 0:
        return None
    diff = abs(assets - (liabilities + equity)) / abs(assets)
    if diff > tolerance:
        return QualityIssue(
            issue_code="ACCOUNTING_IDENTITY",
            metric_name="total_assets",
            period=period,
            details={
                "assets": str(assets),
                "liabilities_plus_equity": str(liabilities + equity),
                "relative_diff": str(diff),
            },
        )
    return None


def check_nonnegative(
    metric: str, value: Decimal, *, period: str | None = None
) -> QualityIssue | None:
    """Flag impossible negatives (e.g. revenue < 0) (DR-028)."""
    if value < 0:
        return QualityIssue(
            issue_code="NEGATIVE_VALUE",
            metric_name=metric,
            period=period,
            details={"value": str(value)},
        )
    return None


def check_yoy_jump(
    metric: str,
    current: Decimal,
    prior: Decimal,
    *,
    period: str | None = None,
    threshold: Decimal = Decimal("5.0"),
) -> QualityIssue | None:
    """Flag a year-over-year change beyond `threshold` (e.g. 5x) for review (DR-028)."""
    if prior == 0:
        return None
    change = abs(current - prior) / abs(prior)
    if change > threshold:
        return QualityIssue(
            issue_code="YOY_JUMP",
            metric_name=metric,
            period=period,
            details={"current": str(current), "prior": str(prior), "change": str(change)},
        )
    return None
