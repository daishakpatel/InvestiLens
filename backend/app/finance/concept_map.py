"""Concept map: canonical metric names -> ordered XBRL tags, with company overrides and
sector applicability (DR-020, DR-042). Source config: `concept_maps/*.yaml` (spec Appendix B/C).

The map is the single most important correctness layer (spec §11): first-available-tag-wins
selection turns inconsistent raw XBRL into canonical values Phase 1c can run formulas over.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml

_CONFIG_DIR = Path(__file__).resolve().parent / "concept_maps"

MetricKind = Literal["flow", "stock"]
UnitFamily = Literal["currency", "per_share", "shares"]


@dataclass(frozen=True)
class ConceptMap:
    """Resolved concept map for one company (defaults merged with any override)."""

    version: str
    sector: str  # applicability key: standard | bank | reit
    _flow: dict[str, list[str]]
    _stock: dict[str, list[str]]
    _units: dict[str, UnitFamily]
    _sector_applicability: dict[str, bool]

    def tags(self, metric: str) -> list[str]:
        """Ordered XBRL tags to try for a canonical metric (first available wins)."""
        return self._flow.get(metric) or self._stock.get(metric) or []

    def kind(self, metric: str) -> MetricKind | None:
        if metric in self._flow:
            return "flow"
        if metric in self._stock:
            return "stock"
        return None

    def unit_family(self, metric: str) -> UnitFamily:
        return self._units.get(metric, "currency")

    def applies(self, metric: str) -> bool:
        """Whether a metric is applicable for this company's sector (DR-001/DR-042)."""
        return self._sector_applicability.get(metric, True)

    @property
    def flow_metrics(self) -> list[str]:
        return list(self._flow)

    @property
    def stock_metrics(self) -> list[str]:
        return list(self._stock)


@lru_cache
def _load_yaml(name: str) -> dict[str, Any]:
    path = _CONFIG_DIR / name
    return yaml.safe_load(path.read_text()) or {}


@lru_cache
def _load_override(ticker: str, cik: str) -> dict[str, Any]:
    for candidate in (f"concept_overrides/{ticker.upper()}.yaml", f"concept_overrides/{cik}.yaml"):
        path = _CONFIG_DIR / candidate
        if path.exists():
            return yaml.safe_load(path.read_text()) or {}
    return {}


def _resolve_sector(sector: str | None, override: dict[str, Any]) -> str:
    if "sector" in override:
        return str(override["sector"])
    aliases = _load_yaml("sector_applicability.yaml").get("sector_aliases", {})
    return str(aliases.get(sector or "", "standard"))


def load_concept_map(*, ticker: str = "", cik: str = "", sector: str | None = None) -> ConceptMap:
    """Build the concept map for a company: defaults, with any override merged on top."""
    base = _load_yaml("concept_map_v1.yaml")
    override = _load_override(ticker, cik) if (ticker or cik) else {}

    flow = {k: list(v) for k, v in base.get("flow_metrics", {}).items()}
    stock = {k: list(v) for k, v in base.get("stock_metrics", {}).items()}
    for metric, tags in override.get("flow_metrics", {}).items():
        flow[metric] = list(tags)  # override replaces the tag list for that metric
    for metric, tags in override.get("stock_metrics", {}).items():
        stock[metric] = list(tags)

    resolved_sector = _resolve_sector(sector, override)
    applicability = _load_yaml("sector_applicability.yaml").get("sectors", {})
    sector_map = applicability.get(resolved_sector, applicability.get("standard", {}))

    return ConceptMap(
        version=str(base.get("version", "v1")),
        sector=resolved_sector,
        _flow=flow,
        _stock=stock,
        _units=base.get("units", {}),
        _sector_applicability=sector_map,
    )
