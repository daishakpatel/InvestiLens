"""Canonical value selection from raw facts (DR-020) and restatement handling (DR-023).

A `FactView` is a provider-agnostic view of a `financial_facts` row (or a parsed companyfacts
entry). Selection walks the concept map's tag list in priority order and returns the first tag
that has a value for the target period, preferring the latest-filed value (restatements).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.finance.concept_map import ConceptMap
from app.finance.periods import is_full_year, is_quarter


@dataclass(frozen=True)
class FactView:
    concept_tag: str
    period_start: date | None
    period_end: date | None
    period_type: str  # duration | instant
    value: Decimal
    unit: str
    accession_number: str
    filed_date: date | None
    is_amended: bool = False


@dataclass(frozen=True)
class Selection:
    metric: str
    value: Decimal
    unit: str
    source_tag: str
    accession_number: str
    filed_date: date | None


def _select_best(candidates: list[FactView]) -> FactView:
    """Choose the authoritative fact among candidates for one metric+period (DR-023).

    An explicit amendment (10-K/A, `is_amended`) supersedes — latest amendment wins. Otherwise
    the as-reported original wins, i.e. the earliest-filed fact: a later filing's rounded
    comparative (e.g. a 10-Q showing the prior fiscal year) must not override the 10-K's annual.
    """
    amended = [f for f in candidates if f.is_amended]
    if amended:
        return max(amended, key=lambda f: f.filed_date or date.min)
    return min(candidates, key=lambda f: f.filed_date or date.max)


def rank_restatements(candidates: list[FactView]) -> list[tuple[FactView, bool]]:
    """Return (fact, is_latest) for each candidate; exactly one is marked latest (DR-023).

    Used when persisting: a restated metric keeps both rows, one flagged `is_latest = true`.
    """
    if not candidates:
        return []
    best = _select_best(candidates)
    return [(f, f is best) for f in candidates]


def select_metric(
    facts: list[FactView],
    concept_map: ConceptMap,
    metric: str,
    *,
    period_end: date,
    quarter: bool = False,
) -> Selection | None:
    """Select the canonical value of `metric` for the period ending `period_end`.

    Flow metrics match a duration fact of the right length ending on `period_end`; stock metrics
    match an instant fact at `period_end`. First tag in priority order with a match wins.
    """
    kind = concept_map.kind(metric)
    if kind is None:
        return None

    for tag in concept_map.tags(metric):
        matches = [
            f
            for f in facts
            if f.concept_tag == tag
            and _period_matches(f, period_end=period_end, kind=kind, quarter=quarter)
        ]
        if matches:
            chosen = _select_best(matches)
            return Selection(
                metric, chosen.value, chosen.unit, tag, chosen.accession_number, chosen.filed_date
            )
    return None


def matching_facts(
    facts: list[FactView], tag: str, *, period_end: date, kind: str, quarter: bool = False
) -> list[FactView]:
    """All facts for a tag matching the period (candidates for restatement ranking)."""
    return [
        f
        for f in facts
        if f.concept_tag == tag
        and _period_matches(f, period_end=period_end, kind=kind, quarter=quarter)
    ]


def _period_matches(fact: FactView, *, period_end: date, kind: str, quarter: bool) -> bool:
    if fact.period_end != period_end:
        return False
    if kind == "stock":
        return fact.period_type == "instant"
    if fact.period_type != "duration":
        return False
    return (
        is_quarter(fact.period_start, fact.period_end)
        if quarter
        else is_full_year(fact.period_start, fact.period_end)
    )
