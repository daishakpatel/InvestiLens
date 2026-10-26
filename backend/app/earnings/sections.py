"""The deterministic sections of a preview or brief, assembled from stored data (FR-EB-004/006).

Nothing here computes a new analytic: quarterly figures are 7b's `financial_metrics` rows read
through 7i's explicit actuals map (a margin is that quarter's two rows), valuation positions are
7h's bands, flags are 7e's, the reaction is 6b's, and the change list is 6b's filing diff and
management-language counts. Each builder returns None when its input is missing; the caller
records why.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from sqlalchemy.orm import Session

from app.api.red_flags import to_item
from app.comparison.bands import valuation_bands
from app.earnings.calendar import Period, label, previous_period, year_ago
from app.filings import topics
from app.filings.diff import DiffItem
from app.filings.earnings import EarningsReaction, earnings_reactions
from app.filings.service import diff_filings, previous_filing
from app.guidance.outcomes import Actual, actual_for
from app.guidance.taxonomy import actual_inputs
from app.ingestion.documents.chunker import PARSER_VERSION
from app.models import Company, Document, Filing
from app.redflags.taxonomy import TAXONOMY_VERSION
from app.repositories import filings as filing_repo
from app.repositories import guidance as guidance_repo
from app.repositories import metrics as metric_repo
from app.repositories import red_flags as flag_repo
from app.schemas.earnings import (
    ChangedPassage,
    MetricRow,
    MetricTable,
    Reaction,
    TopicShift,
    ValuationLine,
    ValuationSnapshot,
    WhatChanged,
)
from app.schemas.red_flags import RedFlagItem

Unit = Literal["usd", "usd_per_share", "ratio"]
# (metric, label, unit): the actuals-map name (7i) or a financial_metrics name.
SNAPSHOT: tuple[tuple[str, str, Unit], ...] = (
    ("revenue", "Revenue", "usd"),
    ("gross_margin", "Gross margin", "ratio"),
    ("operating_margin", "Operating margin", "ratio"),
    ("eps_gaap", "EPS (GAAP, diluted)", "usd_per_share"),
    ("operating_cash_flow", "Operating cash flow", "usd"),
)
VALUATION = (("pe_ratio", "P/E (TTM)"), ("ev_ebitda", "EV/EBITDA (TTM)"))
PERIODIC_MATCH = timedelta(days=7)  # a 10-Q's period end vs the fiscal calendar's quarter end
QUOTE_CHARS = 280
TOP_CHANGES = 3
TOP_TOPICS = 3
_RATIO = Decimal("0.000001")

Rows = dict[str, tuple[Decimal, str]]


def figure(metric: str, rows: Rows) -> Actual | None:
    """One quarter's value of a snapshot metric, with the source IDs of its rows."""
    if metric == "operating_cash_flow":  # a stored row, not in the guidance actuals map
        if metric not in rows:
            return None
        value, source = rows[metric]
        return Actual(value, (source,))
    return actual_for(metric, "usd", rows)  # the unit only matters for percent_of_revenue


def change(current: Decimal, prior: Decimal | None, unit: Unit) -> Decimal | None:
    """Growth for money and per-share figures; the difference in ratio points for margins."""
    if prior is None:
        return None
    if unit == "ratio":
        return (current - prior).quantize(_RATIO)
    return ((current - prior) / abs(prior)).quantize(_RATIO) if prior else None


def quarter_rows(session: Session, company_id: int, wanted: Sequence[Period]) -> dict[Period, Rows]:
    return guidance_repo.actual_rows(
        session, company_id, wanted, actual_inputs() | {"operating_cash_flow"}
    )


def metric_table(session: Session, company_id: int, period: Period) -> MetricTable | None:
    """The quarter's snapshot figures against the prior quarter and the prior-year quarter."""
    prior_q, prior_y = previous_period(period), year_ago(period)
    found = quarter_rows(session, company_id, [period, prior_q, prior_y])
    if period not in found:
        return None
    rows: list[MetricRow] = []
    for metric, name, unit in SNAPSHOT:
        now = figure(metric, found[period])
        before = figure(metric, found.get(prior_q, {}))
        year = figure(metric, found.get(prior_y, {}))
        rows.append(
            MetricRow(
                metric=metric,
                label=name,
                unit=unit,
                change_kind="points" if unit == "ratio" else "growth",
                value=now.value if now else None,
                source_ids=list(now.source_ids) if now else [],
                prior_quarter=before.value if before else None,
                prior_quarter_source_ids=list(before.source_ids) if before else [],
                change_vs_prior_quarter=change(now.value, before.value, unit)
                if now and before
                else None,
                prior_year=year.value if year else None,
                prior_year_source_ids=list(year.source_ids) if year else [],
                change_vs_prior_year=change(now.value, year.value, unit) if now and year else None,
                reason=None if now else f"Not reported for {label(period)}.",
            )
        )
    return MetricTable(
        fiscal_year=period[0],
        fiscal_period=period[1],
        period_label=label(period),
        prior_quarter_label=label(prior_q),
        prior_year_label=label(prior_y),
        rows=rows,
    )


def latest_quarter(session: Session, company_id: int) -> Period | None:
    """The newest quarter with reported revenue."""
    series = metric_repo.get_metric_series(
        session, company_id=company_id, metric_name="revenue", period_type="Q"
    )
    rows = [r for r in series if r.fiscal_year and r.fiscal_quarter and r.metric_value is not None]
    return (rows[-1].fiscal_year or 0, f"Q{rows[-1].fiscal_quarter}") if rows else None


def to_reaction(r: EarningsReaction, ticker: str) -> Reaction:
    source_ids = [f"filing:{r.filing.id}"]
    if r.pre_date and r.post_date:
        source_ids.append(f"price:{ticker}:{r.pre_date.isoformat()}:{r.post_date.isoformat()}")
    return Reaction(
        filing_id=r.filing.id,
        filing_date=r.filing.filing_date,
        pre_date=r.pre_date,
        post_date=r.post_date,
        move_at_open=r.move_at_open,
        move=r.move,
        move_5d=r.move_5d,
        volume_ratio=r.volume_ratio,
        source_ids=source_ids,
        reason=r.reason,
    )


def reaction(session: Session, company: Company, *, filing_id: int | None) -> Reaction | None:
    """The reaction to one earnings 8-K, or (filing_id None) to the newest one."""
    for r in earnings_reactions(session, company_id=company.id):  # newest first
        if filing_id is None or r.filing.id == filing_id:
            return to_reaction(r, company.ticker)
    return None


def valuation_snapshot(session: Session, company: Company) -> ValuationSnapshot | None:
    """P/E and EV/EBITDA today with their positional labels (7h); None without band data."""
    response = valuation_bands(session, company, None)
    bands = {b.multiple: b for b in response.bands}
    latest = {
        m.metric_name: m
        for m in metric_repo.get_latest_metrics(
            session, company_id=company.id, metric_names=[m for m, _ in VALUATION]
        )
        if m.period_type == "LATEST" and m.source_id
    }
    lines = []
    for multiple, name in VALUATION:
        band, row = bands.get(multiple), latest.get(multiple)
        if band is None or band.value is None or row is None or row.source_id is None:
            continue
        lines.append(
            ValuationLine(
                multiple=multiple,
                label=name,
                value=band.value,
                source_ids=[row.source_id],
                own_label=band.own.label,
                own_n=band.own.n,
                peer_label=band.peers.label,
                peer_n=band.peers.n,
            )
        )
    return ValuationSnapshot(as_of=response.as_of, lines=lines) if lines else None


def flags_since(session: Session, company: Company, since: date) -> list[RedFlagItem]:
    """Red flags (7e) filed on or after `since`, newest first."""
    return [
        to_item(flag, filing, ticker)
        for flag, filing, ticker in flag_repo.latest_flags(
            session, company_ids=[company.id], taxonomy_version=TAXONOMY_VERSION, since=since
        )
    ]


def periodic_filing(session: Session, company_id: int, quarter_end: date) -> Filing | None:
    """The parsed 10-Q (or, for a fourth quarter, 10-K) whose period ends with the quarter."""
    for form in ("10-Q", "10-K"):
        for filing in filing_repo.list_filings_by_type(
            session, company_id=company_id, filing_type=form
        ):
            if filing.period_end and abs(filing.period_end - quarter_end) <= PERIODIC_MATCH:
                document = session.get(Document, filing.document_id)
                parsed = document is not None and document.parser_version == PARSER_VERSION
                return filing if parsed else None
    return None


def shorten(text: str, limit: int = QUOTE_CHARS) -> str:
    """`text` cut at a word boundary to at most `limit` characters, with an ellipsis if cut."""
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    if text[limit - 1] != " " and " " in cut:  # mid-word: drop the partial word
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:") + "…"


def _passage(item: DiffItem) -> ChangedPassage:
    unit = item.new or item.old
    return ChangedPassage(
        status=item.status,  # type: ignore[arg-type]  # unchanged items are filtered out
        heading=shorten(unit.heading) if unit else "",
        old_quote=shorten(item.old.text) if item.old else None,
        new_quote=shorten(item.new.text) if item.new else None,
        source_ids=list(
            dict.fromkeys(
                (
                    *(item.new.source_ids if item.new else ()),
                    *(item.old.source_ids if item.old else ()),
                )
            )
        ),
    )


def topic_shifts(session: Session, filing: Filing, against: Filing) -> list[TopicShift]:
    """The management topics whose MD&A intensity moved most between two filings (6b counts)."""
    chunks = filing_repo.get_section_chunks(
        session,
        document_ids=[against.document_id, filing.document_id],
        section_like=topics.MDA_SECTION_LIKE,
        parser_version=PARSER_VERSION,
    )
    before = topics.analyze(c for c in chunks if c.document_id == against.document_id)
    after = topics.analyze(c for c in chunks if c.document_id == filing.document_id)
    if not before.word_count or not after.word_count:
        return []
    shifts = []
    for topic, (name, _) in topics.TOPIC_TAXONOMY.items():
        old = before.topics[topic].per_1k(before.word_count)
        new = after.topics[topic].per_1k(after.word_count)
        cited = after.topics[topic].statements or before.topics[topic].statements
        if old != new and cited:
            sources = list(dict.fromkeys(s.source_id for s in cited))[:3]
            shifts.append(
                TopicShift(
                    topic=topic, label=name, before_per_1k=old, after_per_1k=new, source_ids=sources
                )
            )
    shifts.sort(key=lambda s: (-abs(s.after_per_1k - s.before_per_1k), s.topic))
    return shifts[:TOP_TOPICS]


def risk_changes(session: Session, filing: Filing, against: Filing) -> list[DiffItem]:
    """Risk-factor items that are not unchanged, in the deterministic diff (no model call)."""
    return [
        item
        for item in diff_filings(session, filing, against).items
        if item.status != "unchanged"
        and (item.new or item.old) is not None
        and (item.new or item.old).kind == "risk_factor"  # type: ignore[union-attr]
    ]


def what_changed(session: Session, filing: Filing) -> WhatChanged | None:
    """This 10-Q against the previous 10-Q (a 10-K against the previous 10-K)."""
    against = previous_filing(session, filing)
    if against is None:
        return None
    changes = risk_changes(session, filing, against)
    count = {s: sum(1 for c in changes if c.status == s) for s in ("new", "removed", "reworded")}
    order = {"new": 0, "removed": 1, "reworded": 2}
    top = sorted(changes, key=lambda c: (order[c.status], c.similarity or 0.0))[:TOP_CHANGES]
    return WhatChanged(
        filing_id=filing.id,
        filing_type=filing.filing_type,
        filing_date=filing.filing_date,
        against_filing_id=against.id,
        against_filing_date=against.filing_date,
        new_risks=count["new"],
        removed_risks=count["removed"],
        reworded_risks=count["reworded"],
        top_changes=[_passage(c) for c in top],
        topic_shifts=topic_shifts(session, filing, against),
    )
