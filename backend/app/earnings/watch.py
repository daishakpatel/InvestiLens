"""Watch items for a pre-earnings preview (FR-EB-005, AGT-EB-001).

Candidates are built in code, each with its numbers computed here and its evidence IDs:

(a) a metric whose latest year-over-year growth slowed by more than 5 percentage points;
(d) a margin that moved the same way for two quarters after moving the other way;
(b) risk factors new in the most recent 10-Q/10-K, against the previous one of the same form;
(c) the management topic whose MD&A intensity rose most between those filings.

The model may only reword a candidate in one sentence. A rewording is used only if it is one
sentence with exactly the candidate's numbers and no advice, prediction or characterisation;
otherwise the candidate's own sentence is shown. No candidate, no watch items.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.citation.advice import characterises_guidance, contains_advice, predicts
from app.citation.extract import extract_numbers, split_claims
from app.config import Settings
from app.earnings import prompt
from app.earnings.calendar import Period, label, previous_period, year_ago
from app.earnings.sections import figure, risk_changes, shorten, topic_shifts
from app.filings.service import previous_filing
from app.finance.display import format_metric_value
from app.ingestion.documents.chunker import PARSER_VERSION
from app.models import Company, Filing
from app.providers.base import LLMClient
from app.repositories import filings as filing_repo
from app.repositories import guidance as guidance_repo
from app.schemas.earnings import WatchItem

MAX_ITEMS = 5
DECELERATION = Decimal("0.05")  # 5 percentage points of year-over-year growth
GROWTH_METRICS = (
    ("revenue", "Revenue"),
    ("operating_income", "Operating income"),
    ("net_income", "Net income"),
)
MARGINS = (("gross_margin", "Gross margin"), ("operating_margin", "Operating margin"))
MAX_NEW_RISKS = 2
_MAX_CHARS = 400
_HEADING_CHARS = 140


@dataclass(frozen=True)
class Candidate:
    kind: str
    text: str
    source_ids: tuple[str, ...]


def pct(value: Decimal) -> str:
    return format_metric_value(value, "ratio")


def _growth(
    rows: dict[Period, dict[str, tuple[Decimal, str]]], period: Period, metric: str
) -> tuple[Decimal, tuple[str, ...]] | None:
    now, ago = rows.get(period, {}).get(metric), rows.get(year_ago(period), {}).get(metric)
    if now is None or ago is None or ago[0] <= 0:
        return None  # growth off a loss or zero says nothing
    return (now[0] - ago[0]) / ago[0], (now[1], ago[1])


def decelerations(session: Session, company_id: int, latest: Period) -> list[Candidate]:
    prior = previous_period(latest)
    wanted = [latest, prior, year_ago(latest), year_ago(prior)]
    rows = guidance_repo.actual_rows(session, company_id, wanted, [m for m, _ in GROWTH_METRICS])
    out = []
    for metric, name in GROWTH_METRICS:
        now, before = _growth(rows, latest, metric), _growth(rows, prior, metric)
        if now is None or before is None or before[0] - now[0] <= DECELERATION:
            continue
        out.append(
            Candidate(
                kind="growth_deceleration",
                text=f"{name} growth slowed to {pct(now[0])} year over year in {label(latest)}, "
                f"from {pct(before[0])} in {label(prior)}.",
                source_ids=(*now[1], *before[1]),
            )
        )
    return out


def margin_reversals(session: Session, company_id: int, latest: Period) -> list[Candidate]:
    quarters = [latest]
    for _ in range(3):
        quarters.insert(0, previous_period(quarters[0]))
    rows = guidance_repo.actual_rows(
        session, company_id, quarters, {"revenue", "gross_profit", "operating_income"}
    )
    out = []
    for metric, name in MARGINS:
        values = [figure(metric, rows.get(q, {})) for q in quarters]
        if any(v is None for v in values):
            continue
        m = [v.value for v in values if v is not None]
        steps = [m[1] - m[0], m[2] - m[1], m[3] - m[2]]
        if not all(steps) or (steps[1] > 0) != (steps[2] > 0) or (steps[0] > 0) == (steps[1] > 0):
            continue
        went, before = ("rose", "falling") if steps[2] > 0 else ("fell", "rising")
        out.append(
            Candidate(
                kind="margin_reversal",
                text=f"{name} {went} for two quarters in a row, to {pct(m[3])} in "
                f"{label(quarters[3])} from {pct(m[1])} in {label(quarters[1])}, after "
                f"{before} in {label(quarters[1])}.",
                source_ids=tuple(
                    dict.fromkeys(s for v in values[1:] if v is not None for s in v.source_ids)
                ),
            )
        )
    return out


def latest_periodic(session: Session, company_id: int) -> tuple[Filing, Filing] | None:
    """(newest parsed 10-Q or 10-K, the previous filing of that form), or None."""
    latest = [
        f
        for f in (
            filing_repo.get_latest_filing(
                session, company_id=company_id, filing_type=form, parser_version=PARSER_VERSION
            )
            for form in ("10-Q", "10-K")
        )
        if f is not None and f.filing_date is not None
    ]
    if not latest:
        return None
    filing = max(latest, key=lambda f: (f.filing_date, f.id))
    against = previous_filing(session, filing)
    return (filing, against) if against else None


def filing_candidates(session: Session, filing: Filing, against: Filing) -> list[Candidate]:
    form, filed = filing.filing_type, filing.filing_date.isoformat() if filing.filing_date else ""
    out = []
    for item in [c for c in risk_changes(session, filing, against) if c.status == "new"][
        :MAX_NEW_RISKS
    ]:
        unit = item.new
        if unit is None or not unit.source_ids:
            continue
        heading = shorten(unit.heading, _HEADING_CHARS)
        out.append(
            Candidate(
                kind="new_risk_factor",
                text=f"The {form} filed {filed} adds a risk factor not in the prior {form}: "
                f"“{heading}”.",
                source_ids=tuple(unit.source_ids),
            )
        )
    rises = [s for s in topic_shifts(session, filing, against) if s.after_per_1k > s.before_per_1k]
    if rises:
        top = max(rises, key=lambda s: (s.after_per_1k - s.before_per_1k, s.topic))
        out.append(
            Candidate(
                kind="topic_rise",
                text=f"Mentions of {top.label.lower()} in MD&A rose to {top.after_per_1k:g} per "
                f"1,000 words in the {form} filed {filed}, from {top.before_per_1k:g} in the "
                f"prior {form}.",
                source_ids=tuple(top.source_ids),
            )
        )
    return out


def candidates(session: Session, company: Company, latest: Period | None) -> list[Candidate]:
    """All deterministic candidates, in the order (a), (d), (b), (c), capped at five."""
    found: list[Candidate] = []
    if latest is not None:
        found += decelerations(session, company.id, latest)
        found += margin_reversals(session, company.id, latest)
    pair = latest_periodic(session, company.id)
    if pair is not None:
        found += filing_candidates(session, *pair)
    return [c for c in found if c.source_ids][:MAX_ITEMS]


def _numbers(text: str) -> Counter[tuple[str, str]]:
    return Counter(
        (t.kind, str(t.value.normalize()) if t.value is not None else t.raw)
        for t in extract_numbers(text)
    )


def acceptable_rewording(original: str, text: Any) -> bool:
    """One sentence, the original's exact numbers, and nothing the guards reject."""
    if not isinstance(text, str) or not text.strip() or len(text) > _MAX_CHARS:
        return False
    text = text.strip()
    return (
        len(split_claims(text)) == 1
        and _numbers(text) == _numbers(original)
        and not contains_advice(text)
        and not predicts(text)
        and not characterises_guidance(text)
    )


def reworded(raw: dict[str, Any] | None, items: Sequence[WatchItem]) -> dict[int, str]:
    """Item index -> accepted rewording, from the model's JSON (anything else is ignored)."""
    proposed = raw.get("items") if raw else None
    out: dict[int, str] = {}
    for entry in proposed if isinstance(proposed, list) else []:
        if not isinstance(entry, dict):
            continue
        key = str(entry.get("id", ""))
        index = int(key[1:]) - 1 if key[:1] == "w" and key[1:].isdigit() else -1
        if 0 <= index < len(items) and acceptable_rewording(items[index].text, entry.get("text")):
            out[index] = str(entry["text"]).strip()
    return out


def watch_items(session: Session, company: Company, latest: Period | None) -> list[WatchItem]:
    """The deterministic watch list: each candidate's own sentence and evidence IDs."""
    return [
        WatchItem(kind=c.kind, text=c.text, source_ids=list(c.source_ids))  # type: ignore[arg-type]
        for c in candidates(session, company, latest)
    ]


def reword(
    session: Session,
    items: list[WatchItem],
    *,
    llm: LLMClient,
    settings: Settings,
    user_id: int | None = None,
) -> list[WatchItem]:
    """The model's one-sentence rewordings where they pass the checks; the rest unchanged."""
    if not items:
        return items
    lines = [
        prompt.line([f"w{i}"], item.text, untrusted=item.kind == "new_risk_factor", key="id")
        for i, item in enumerate(items, 1)
    ]
    raw = prompt.call(
        session, llm, settings, prompt.messages(prompt.WATCH_TASK, lines), user_id=user_id
    )
    texts = reworded(raw, items)
    return [
        item.model_copy(update={"text": texts[i], "reworded": True}) if i in texts else item
        for i, item in enumerate(items)
    ]
