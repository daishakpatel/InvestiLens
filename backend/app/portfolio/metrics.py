"""Deterministic portfolio aggregates: weighted metrics, sector exposure, concentration (§37.2).

Pure functions over normalized weights and per-holding values — no DB, no LLM. The same formulas
are mirrored client-side for what-if recompute; keeping them simple keeps the two in agreement.
"""

from __future__ import annotations

from decimal import Decimal

from app.portfolio.weights import NormalizedWeight
from app.schemas.portfolio import Concentration, SectorExposure, WeightedMetric

_RATIO_PRECISION = Decimal("0.00000001")
_UNKNOWN_SECTOR = "Unknown"


def weighted_metric(
    metric_name: str,
    unit: str,
    values: dict[str, Decimal | None],
    weights: list[NormalizedWeight],
) -> WeightedMetric:
    """Portfolio-weighted value, renormalizing over the holdings that actually have a value.

    `coverage` is the fraction of total weight that contributed; 0 coverage → NULL value + a reason
    code, never a misleading 0 (DR-041 spirit).
    """
    covered = [w for w in weights if values.get(w.ticker) is not None]
    coverage = sum((w.weight for w in covered), Decimal(0))
    if coverage <= 0:
        return WeightedMetric(
            metric_name=metric_name,
            unit=unit,
            value=None,
            coverage=Decimal(0),
            warnings=["NO_COVERAGE"],
        )
    total = sum(
        ((w.weight / coverage) * values[w.ticker] for w in covered),  # type: ignore[operator]
        Decimal(0),
    )
    warnings = [] if coverage == Decimal(1) else ["PARTIAL_COVERAGE"]
    return WeightedMetric(
        metric_name=metric_name,
        unit=unit,
        value=total.quantize(_RATIO_PRECISION),
        coverage=coverage,
        warnings=warnings,
    )


def sector_exposure(
    sectors: dict[str, str | None], weights: list[NormalizedWeight]
) -> list[SectorExposure]:
    """Sum normalized weight by sector (unknown sectors bucketed), largest first."""
    totals: dict[str, Decimal] = {}
    for w in weights:
        sector = sectors.get(w.ticker) or _UNKNOWN_SECTOR
        totals[sector] = totals.get(sector, Decimal(0)) + w.weight
    return [
        SectorExposure(sector=s, weight=v)
        for s, v in sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def concentration(weights: list[NormalizedWeight]) -> Concentration:
    """Herfindahl-Hirschman Index (sum of squared weights) and effective holding count (1/HHI)."""
    hhi = sum((w.weight * w.weight for w in weights), Decimal(0)).quantize(_RATIO_PRECISION)
    top = max(weights, key=lambda w: w.weight) if weights else None
    effective = (Decimal(1) / hhi).quantize(_RATIO_PRECISION) if hhi > 0 else Decimal(0)
    return Concentration(
        hhi=hhi,
        effective_holdings=effective,
        top_holding=top.ticker if top else None,
        top_weight=top.weight if top else None,
    )
