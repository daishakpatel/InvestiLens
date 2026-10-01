"""Inline XBRL (iXBRL) extraction and cross-check (DP-002).

Parses `ix:nonfraction` facts embedded in the filing HTML and cross-checks them against the
separately-ingested `companyfacts` values (Phase 1a/1b). Discrepancies are FLAGGED, never
silently resolved — the caller records them in `data_quality_issues`.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from selectolax.parser import HTMLParser


@dataclass(frozen=True)
class IxFact:
    concept: str  # e.g. "us-gaap:Revenues"
    value: Decimal
    context_ref: str | None


def _parse_value(text: str, scale: str | None, sign: str | None) -> Decimal | None:
    cleaned = text.strip().replace(",", "").replace("$", "").replace("%", "").replace("(", "-")
    cleaned = cleaned.replace(")", "")
    if not cleaned or cleaned in {"-", "—"}:
        return None
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    if scale:
        with contextlib.suppress(InvalidOperation, ValueError):
            value *= Decimal(10) ** int(scale)
    if sign == "-":
        value = -value
    return value


def extract_ixbrl_facts(html: str) -> list[IxFact]:
    """Extract numeric inline-XBRL facts from filing HTML."""
    tree = HTMLParser(html)
    facts: list[IxFact] = []
    root = tree.root
    if root is None:
        return facts
    for node in root.traverse(include_text=False):
        if node.tag != "ix:nonfraction":  # namespaced tag; CSS can't select a colon
            continue
        name = node.attributes.get("name")
        if not name:
            continue
        value = _parse_value(
            node.text(deep=True) or "", node.attributes.get("scale"), node.attributes.get("sign")
        )
        if value is not None:
            facts.append(
                IxFact(concept=name, value=value, context_ref=node.attributes.get("contextref"))
            )
    return facts


@dataclass(frozen=True)
class Discrepancy:
    concept: str
    ixbrl_value: Decimal
    companyfacts_value: Decimal
    relative_diff: Decimal


def cross_check(
    ix_facts: list[IxFact],
    companyfacts_values: dict[str, Decimal],
    *,
    tolerance: Decimal = Decimal("0.01"),
) -> list[Discrepancy]:
    """Flag concepts whose iXBRL value disagrees with companyfacts beyond a relative tolerance."""
    discrepancies: list[Discrepancy] = []
    seen: set[str] = set()
    for fact in ix_facts:
        expected = companyfacts_values.get(fact.concept)
        if expected is None or expected == 0 or fact.concept in seen:
            continue
        seen.add(fact.concept)
        diff = abs(fact.value - expected) / abs(expected)
        if diff > tolerance:
            discrepancies.append(Discrepancy(fact.concept, fact.value, expected, diff))
    return discrepancies
