"""Guidance against actuals, in pure Python and Decimal (FR-GD-007..012, DR-GD-001..003).

- A non-GAAP guide is never compared with a GAAP actual (`not_comparable`, DR-GD-001); neither is
  a guide whose basis was not stated, unless the metric has no customary non-GAAP version.
- The actual comes from the same fiscal period's rows through the explicit `ACTUALS` table; a
  missing input gives `actual_unavailable`, never zero (DR-GD-002).
- A single figure is a range of one value: anything but that exact figure is above or below it.
- Revisions: the first guidance for a (period, metric, basis) is the headline; later releases'
  guidance for it supersede it in a chain, and are listed as revisions (FR-GD-009).
- The track record counts headline quarterly revenue outcomes over the last 8 guided quarters and
  is shown only from 4 comparable ones (FR-GD-011). Its wording is positional (FR-GD-012).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

from app.guidance.taxonomy import ACTUALS, UNSPECIFIED_COMPARABLE

Result = Literal[
    "above_range", "within_range", "below_range", "not_comparable", "actual_unavailable"
]
COMPARED: tuple[Result, ...] = ("above_range", "within_range", "below_range")
TRACK_QUARTERS = 8
MIN_COMPARABLE = 4


@dataclass(frozen=True)
class Guided:
    metric: str
    basis: str
    unit: str
    low: Decimal | None
    high: Decimal | None
    point: Decimal | None

    @property
    def bounds(self) -> tuple[Decimal, Decimal]:
        if self.point is not None:
            return self.point, self.point
        if self.low is None or self.high is None:
            raise ValueError("guidance has neither a point nor a full range")
        return self.low, self.high


@dataclass(frozen=True)
class Actual:
    value: Decimal
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class Outcome:
    result: Result
    actual: Actual | None = None
    delta_vs_low: Decimal | None = None
    delta_vs_high: Decimal | None = None
    delta_vs_mid: Decimal | None = None
    delta_vs_mid_pct: Decimal | None = None
    reason_code: str | None = None


def actual_for(metric: str, unit: str, rows: Mapping[str, tuple[Decimal, str]]) -> Actual | None:
    """The GAAP actual for `metric` from one period's `rows` (name -> (value, source_id))."""
    formula = ACTUALS.get(metric)
    if formula is None or any(name not in rows for name in formula[::2]):
        return None
    value, source = rows[formula[0]]
    sources = [source]
    if len(formula) == 3:
        other, other_source = rows[formula[2]]
        sources.append(other_source)
        if formula[1] == "/":
            if other == 0:
                return None
            value = value / other
        else:
            value = value - other
    if unit == "percent_of_revenue":
        if "revenue" not in rows or rows["revenue"][0] == 0:
            return None
        value = value / rows["revenue"][0]
        sources.append(rows["revenue"][1])
    return Actual(value, tuple(dict.fromkeys(sources)))


def compute_outcome(item: Guided, actual: Actual | None) -> Outcome:
    if item.basis == "non_gaap" or item.metric == "eps_non_gaap":
        return Outcome("not_comparable", reason_code="non_gaap_basis")
    if item.basis != "gaap" and item.metric not in UNSPECIFIED_COMPARABLE:
        return Outcome("not_comparable", reason_code="basis_unspecified")
    if actual is None:
        return Outcome("actual_unavailable", reason_code="actual_not_reported")
    low, high = item.bounds
    mid = (low + high) / 2
    value = actual.value
    result: Result = (
        "above_range" if value > high else "below_range" if value < low else "within_range"
    )
    delta_mid = value - mid
    return Outcome(
        result,
        actual,
        delta_vs_low=value - low,
        delta_vs_high=value - high,
        delta_vs_mid=delta_mid,
        delta_vs_mid_pct=delta_mid / abs(mid) if mid != 0 else None,
    )


@dataclass(frozen=True)
class Issued:
    """What revision chaining needs of a verified item."""

    id: int
    key: tuple[int, str, str, str]  # (fiscal_year, fiscal_period, metric, basis)
    issued_at: datetime | None


def revision_chain(items: Sequence[Issued]) -> dict[int, int | None]:
    """item id -> the id of the next release's guidance for the same key (None for the last)."""
    groups: dict[tuple[int, str, str, str], list[Issued]] = defaultdict(list)
    for item in items:
        groups[item.key].append(item)
    chain: dict[int, int | None] = {}
    for group in groups.values():
        group.sort(key=lambda i: (i.issued_at.timestamp() if i.issued_at else 0.0, i.id))
        for current, following in zip(group, [*group[1:], None], strict=True):
            chain[current.id] = following.id if following else None
    return chain


@dataclass(frozen=True)
class TrackRecord:
    n_quarters: int  # guided quarters looked at (up to 8)
    n_comparable: int
    n_above: int
    n_within: int
    n_below: int
    avg_delta_vs_mid: Decimal | None
    avg_delta_vs_mid_pct: Decimal | None
    sufficient: bool
    label: str


def track_record(
    headlines: Sequence[tuple[tuple[int, str], Outcome]], *, metric_label: str = "Revenue"
) -> TrackRecord:
    """Over the latest `TRACK_QUARTERS` guided quarters ((fiscal_year, "Qn"), headline outcome)."""
    latest = sorted(headlines, key=lambda h: h[0], reverse=True)[:TRACK_QUARTERS]
    compared = [o for _, o in latest if o.result in COMPARED]
    counts = {r: sum(1 for o in compared if o.result == r) for r in COMPARED}
    n = len(compared)
    deltas = [o.delta_vs_mid for o in compared if o.delta_vs_mid is not None]
    pcts = [o.delta_vs_mid_pct for o in compared if o.delta_vs_mid_pct is not None]
    sufficient = n >= MIN_COMPARABLE
    if sufficient:
        label = (
            f"{metric_label} came in above the guided range in {counts['above_range']} of {n} "
            f"quarters, within it in {counts['within_range']} and below it in "
            f"{counts['below_range']}."
        )
    else:
        label = f"Insufficient history (n={n})"
    return TrackRecord(
        n_quarters=len(latest),
        n_comparable=n,
        n_above=counts["above_range"],
        n_within=counts["within_range"],
        n_below=counts["below_range"],
        avg_delta_vs_mid=sum(deltas, Decimal(0)) / len(deltas) if deltas else None,
        avg_delta_vs_mid_pct=sum(pcts, Decimal(0)) / len(pcts) if pcts else None,
        sufficient=sufficient,
        label=label,
    )
