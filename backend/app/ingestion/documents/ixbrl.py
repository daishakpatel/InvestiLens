"""Inline XBRL (iXBRL) extraction and cross-check (DP-002).

Parses `ix:nonfraction` facts embedded in the filing HTML and cross-checks them against the
separately-ingested `companyfacts` values (Phase 1a/1b). Discrepancies are FLAGGED, never
silently resolved — the caller records them in `data_quality_issues`.

`tagged_values` also reads each fact's context (period and dimension members) and numeric
`ix:nonnumeric` durations ("8.8" years), which companyfacts leaves out: footnote facts such as a
per-note debt schedule or a lease term exist only here (Phase 7f, ADR-0044).
"""

from __future__ import annotations

import contextlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

from selectolax.parser import HTMLParser, Node


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


@dataclass(frozen=True)
class IxContext:
    period_end: date | None  # the instant, or a duration's end date
    members: Mapping[str, str] = field(default_factory=dict)  # dimension -> member


@dataclass(frozen=True)
class IxValue:
    concept: str
    value: Decimal
    context: IxContext


def _date(text: str) -> date | None:
    try:
        return date.fromisoformat(text.strip())
    except ValueError:
        return None


def _descendants(node: Node) -> list[Node]:
    out: list[Node] = []
    for child in node.iter(include_text=False):  # direct children; `traverse` runs past the node
        out.append(child)
        out.extend(_descendants(child))
    return out


def _contexts(root: Node) -> dict[str, IxContext]:
    contexts: dict[str, IxContext] = {}
    for node in root.traverse(include_text=False):
        if node.tag != "xbrli:context" or not node.attributes.get("id"):
            continue
        end: date | None = None
        members: dict[str, str] = {}
        for child in _descendants(node):
            if child.tag in ("xbrli:instant", "xbrli:enddate"):
                end = _date(child.text())
            elif child.tag == "xbrldi:explicitmember" and child.attributes.get("dimension"):
                members[str(child.attributes["dimension"])] = child.text().strip()
        contexts[str(node.attributes["id"])] = IxContext(end, members)
    return contexts


def tagged_values(html: str) -> list[IxValue]:
    """Every numeric fact with its context: `ix:nonfraction` values and `ix:nonnumeric` values
    that read as a number (a duration in years). Text facts ("five-year") are skipped."""
    root = HTMLParser(html).root
    if root is None:
        return []
    contexts = _contexts(root)
    values: list[IxValue] = []
    for node in root.traverse(include_text=False):
        if node.tag not in ("ix:nonfraction", "ix:nonnumeric"):
            continue
        name, ref = node.attributes.get("name"), node.attributes.get("contextref")
        context = contexts.get(str(ref))
        if not name or context is None:
            continue
        text = node.text(deep=True) or ""
        if node.tag == "ix:nonfraction":
            value = _parse_value(text, node.attributes.get("scale"), node.attributes.get("sign"))
        else:
            value = _parse_value(text, None, None)
        if value is not None:
            values.append(IxValue(name, value, context))
    return values


def text_values(html: str, concept: str) -> list[str]:
    """The text of every `ix:nonnumeric` fact named `concept` ("ecd:PeoName"), in order."""
    root = HTMLParser(html).root
    if root is None:
        return []
    return [
        " ".join((node.text(deep=True) or "").split())
        for node in root.traverse(include_text=False)
        if node.tag == "ix:nonnumeric" and node.attributes.get("name") == concept
    ]
