"""The post-earnings brief's short narrative (FR-EB-006, CIT-EB-001..003, AGT-EB-001/002).

The model is shown the brief's own sections as lines, each with the backend source IDs it came
from, and asked for at most 4 cited sentences. Every sentence then goes through the standard
claim verifier (`citation.verify_claims`) against those same lines; a sentence is kept only if it
is accepted (or softened), cites at least one ID, and passes the advice, prediction and
guidance-characterisation guards. Dropped sentences shorten the narrative: nothing is generated
to replace them, and at most 4 sentences and 120 words are kept.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy.orm import Session

from app.citation.advice import characterises_guidance, contains_advice, predicts
from app.citation.evidence import EvidenceItem
from app.citation.extract import RawClaim, strip_markers
from app.citation.pipeline import verify_claims
from app.config import Settings
from app.earnings import prompt
from app.finance.display import format_metric_value
from app.guidance.alerts import shown_value
from app.providers.base import LLMClient
from app.schemas.earnings import EarningsBrief, MetricRow, Narrative, NarrativeSentence
from app.schemas.sources import TextChunkSource

MAX_SENTENCES = 4
MAX_WORDS = 120
_KEPT = ("accepted", "softened")
_RESULT_WORDS = {
    "above_range": "above the guided range",
    "within_range": "within the guided range",
    "below_range": "below the guided range",
    "not_comparable": "not comparable with the GAAP actual",
    "actual_unavailable": "actual not reported yet",
}
Line = tuple[list[str], str, bool]  # (source IDs, text, holds untrusted filing words)


def shown(value: Any, unit: str) -> str:
    units = {"usd": "USD", "usd_per_share": "USD/shares", "ratio": "ratio"}
    return format_metric_value(value, units.get(unit, unit))


def _change(value: Any, kind: str) -> str:
    if value is None:
        return "n/a"
    if kind == "points":
        return f"{value * 10000:+.0f} basis points"
    return f"{'+' if value >= 0 else ''}{format_metric_value(value, 'ratio')}"


def _metric_line(row: MetricRow, period: str, prior_q: str, prior_y: str) -> Line | None:
    if row.value is None:
        return None
    parts = [f"{row.label} for {period} was {shown(row.value, row.unit)}"]
    if row.prior_quarter is not None:
        parts.append(
            f"versus {shown(row.prior_quarter, row.unit)} in the prior quarter, {prior_q} "
            f"({_change(row.change_vs_prior_quarter, row.change_kind)})"
        )
    if row.prior_year is not None:
        parts.append(
            f"versus {shown(row.prior_year, row.unit)} in the prior-year quarter, {prior_y} "
            f"({_change(row.change_vs_prior_year, row.change_kind)})"
        )
    ids = [*row.source_ids, *row.prior_quarter_source_ids, *row.prior_year_source_ids]
    return list(dict.fromkeys(ids)), "; ".join(parts) + ".", False


def lines(brief: EarningsBrief) -> list[Line]:
    """The brief's sections as cited lines: the narrative's only input (FR-EB-010)."""
    out: list[Line] = []
    table = brief.headline_table
    if table is not None:
        for row in table.rows:
            found = _metric_line(
                row, table.period_label, table.prior_quarter_label, table.prior_year_label
            )
            if found:
                out.append(found)
    for g in brief.versus_guidance:
        outcome = g.outcome
        if outcome is None:
            continue
        low = g.point if g.point is not None else g.low
        high = g.point if g.point is not None else g.high
        guided = shown_value(low, g.unit, g.metric)
        if high != low:
            guided += f" to {shown_value(high, g.unit, g.metric)}"
        actual = (
            f"; the actual was {shown_value(outcome.actual_value, g.unit, g.metric)}"
            if outcome.actual_value is not None
            else ""
        )
        out.append(
            (
                [g.source_id, *outcome.actual_source_ids],
                f"{g.metric_label} for {g.period_label} (guided {guided}) came in "
                f"{_RESULT_WORDS[outcome.result]}{actual}.",
                False,
            )
        )
    r = brief.reaction
    if r is not None and r.move is not None:
        text = (
            f"From the close before the earnings 8-K to the first close after it, the share price "
            f"moved {_change(r.move, 'growth')}"
        )
        if r.move_5d is not None:
            text += f", and {_change(r.move_5d, 'growth')} over five sessions"
        out.append((r.source_ids, text + ".", False))
    w = brief.what_changed
    if w is not None:
        out.append(
            (
                [f"filing:{w.filing_id}", f"filing:{w.against_filing_id}"],
                f"Against the prior {w.filing_type}, the {w.filing_type} has {w.new_risks} new, "
                f"{w.removed_risks} removed and {w.reworded_risks} reworded risk factors.",
                False,
            )
        )
        for passage in w.top_changes:
            out.append(
                (passage.source_ids, f"{passage.status} risk factor: {passage.heading}", True)
            )
        for shift in w.topic_shifts:
            out.append(
                (
                    shift.source_ids,
                    f"MD&A mentions of {shift.label.lower()} went from {shift.before_per_1k:g} to "
                    f"{shift.after_per_1k:g} per 1,000 words.",
                    False,
                )
            )
    for flag in brief.new_flags:
        out.append(([flag.source_id], f"{flag.label} ({flag.event_date}): {flag.snippet}", True))
    return [line for line in out if line[0]]


def evidence(found: Iterable[Line]) -> dict[str, EvidenceItem]:
    """One evidence item per source ID, holding every line that cites it."""
    texts: dict[str, list[str]] = {}
    for ids, text, _ in found:
        for sid in ids:
            texts.setdefault(sid, []).append(text)
    return {
        sid: EvidenceItem(
            source=TextChunkSource(source_id=sid, tier=1, document_id="", text=" ".join(t)),
            text=" ".join(t),
            retrieval_score=0.9,
        )
        for sid, t in texts.items()
    }


def proposed(raw: dict[str, Any] | None) -> list[RawClaim]:
    sentences = raw.get("sentences") if raw else None
    claims = []
    for i, item in enumerate(sentences if isinstance(sentences, list) else []):
        if not isinstance(item, dict) or not isinstance(item.get("text"), str):
            continue
        text, marked = strip_markers(item["text"])
        ids = item.get("source_ids")
        cited = [str(s) for s in ids] if isinstance(ids, list) else []
        claims.append(RawClaim(f"n{i}", text, list(dict.fromkeys([*cited, *marked]))))
    return claims[: MAX_SENTENCES * 2]  # a model that over-produces is not rewarded with more


def kept(text: str) -> bool:
    return not (contains_advice(text) or predicts(text) or characterises_guidance(text))


def capped(sentences: list[NarrativeSentence]) -> list[NarrativeSentence]:
    """At most 4 sentences and 120 words, dropping from the end (never rewriting)."""
    out = sentences[:MAX_SENTENCES]
    while out and sum(len(s.text.split()) for s in out) > MAX_WORDS:
        out.pop()
    return out


def narrative(
    session: Session,
    brief: EarningsBrief,
    *,
    llm: LLMClient,
    settings: Settings,
    user_id: int | None = None,
) -> Narrative | None:
    """The verified narrative, or None when no sentence survives (the section then says so)."""
    found = lines(brief)
    if not found:
        return None
    raw = prompt.call(
        session,
        llm,
        settings,
        prompt.messages(
            prompt.NARRATIVE_TASK,
            [prompt.line(ids, text, untrusted=untrusted) for ids, text, untrusted in found],
        ),
        user_id=user_id,
    )
    claims = proposed(raw)
    verified = verify_claims(claims, evidence(found), settings=settings)
    sentences = capped(
        [
            NarrativeSentence(text=c.text, source_ids=c.source_ids)
            for c in verified.claims
            if c.status in _KEPT and c.source_ids and kept(c.text)
        ]
    )
    if not sentences:
        return None
    return Narrative(
        sentences=sentences,
        dropped=len(claims) - len(sentences),
        prompt_version=prompt.PROMPT_VERSION,
        model=prompt.label(settings),
    )
