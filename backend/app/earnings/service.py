"""Generate and store earnings previews and briefs (FR-EB-004..012, ADR-0048).

1. The calendar is refreshed and the quarter chosen: the next unreported one for a preview, the
   latest reported one for a brief.
2. Every deterministic section is assembled from stored data. A section without its input is
   listed in `missing` with a plain reason ("10-Q not yet filed"), never filled with prose.
3. `inputs_hash` hashes that assembled content: the IDs and values of every input. The same hash
   returns the stored version without a model call (idempotent); a new hash adds the next
   version and keeps the old ones for audit.
4. Only then is the model asked to reword watch items (preview) or write the narrative (brief),
   both checked in code; a failed check drops the text, it never invents a replacement.

Cost guard: only watched or seed companies, and at most `earnings_brief_daily_cap` new versions
a day (logged when reached).
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.earnings import narrative, sections, watch
from app.earnings.calendar import (
    Period,
    build_calendar,
    label,
    latest_reported,
    previous_period,
    quarter_ends,
    upcoming_event,
)
from app.earnings.prompt import PROMPT_VERSION
from app.earnings.prompt import label as model_label
from app.guidance.extract import company_calendar
from app.guidance.service import guidance, track_record
from app.models import Company, EarningsBrief, EarningsEvent
from app.providers import get_llm_client
from app.providers.base import LLMClient
from app.repositories import earnings as repo
from app.repositories import filings as filing_repo
from app.schemas.earnings import BriefHeader, EarningsPreview, Missing, StoredBrief
from app.schemas.earnings import EarningsBrief as BriefContent
from app.schemas.guidance import GuidanceRow
from app.thesis.links import refresh_company_theses
from app.utils.logging import get_logger, log_event

logger = get_logger(__name__)

Kind = Literal["preview", "brief"]
OPEN_FLAG_DAYS = 90
SCOPE = (
    "Figures are the company's reported numbers and its own guidance; no analyst estimates are "
    "used. A preview lists what to watch, never what will happen."
)


class BriefUnavailable(Exception):
    """A brief cannot be made now; `code` says why (the API maps it to a status)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def header(company: Company, event: EarningsEvent) -> BriefHeader:
    return BriefHeader(
        ticker=company.ticker,
        company_name=company.name,
        fiscal_year=event.fiscal_year,
        fiscal_period=event.fiscal_period,
        period_label=label((event.fiscal_year, event.fiscal_period)),
        report_date=event.report_date,
        report_time=event.report_time,  # type: ignore[arg-type]  # CHECK report_time_known
        date_source=event.source,  # type: ignore[arg-type]  # CHECK source_known
        date_estimated=event.source == "estimated",
        date_source_id=event.source_id,
    )


def period_guidance(session: Session, company: Company, period: Period) -> list[GuidanceRow]:
    """The initial guidance (with revisions) the company gave for one quarter (7i)."""
    rows = guidance(session, company, fiscal_year=period[0]).items
    return [row for row in rows if row.fiscal_period == period[1]]


def _filing_id(event: EarningsEvent) -> int | None:
    sid = event.source_id or ""
    return int(sid[len("filing:") :]) if sid.startswith("filing:") else None


def assemble_preview(
    session: Session, company: Company, event: EarningsEvent, *, today: date
) -> EarningsPreview:
    period = (event.fiscal_year, event.fiscal_period)
    last = previous_period(period)
    missing: list[Missing] = []
    snapshot = sections.metric_table(session, company.id, last)
    if snapshot is None:
        missing.append(
            Missing(section="last_quarter_snapshot", reason=f"No figures for {label(last)}.")
        )
    guided = period_guidance(session, company, period)
    if not guided:
        missing.append(
            Missing(
                section="guidance_for_period",
                reason=f"No company guidance found for {label(period)}.",
            )
        )
    record = track_record(session, company)
    if not record.sufficient:
        missing.append(Missing(section="track_record", reason=record.label))
    valuation = sections.valuation_snapshot(session, company)
    if valuation is None:
        missing.append(
            Missing(
                section="valuation_snapshot",
                reason="Valuation bands are not built for this company.",
            )
        )
    reaction = sections.reaction(session, company, filing_id=None)
    if reaction is None or reaction.move is None:
        missing.append(
            Missing(section="last_reaction", reason="No price data around the last earnings 8-K.")
        )
        reaction = None
    return EarningsPreview(
        header=header(company, event),
        last_quarter_snapshot=snapshot,
        guidance_for_period=guided,
        track_record=record if record.sufficient else None,
        valuation_snapshot=valuation,
        open_flags=sections.flags_since(session, company, today - timedelta(days=OPEN_FLAG_DAYS)),
        last_reaction=reaction,
        watch_items=watch.watch_items(session, company, last if snapshot else None),
        missing=missing,
    )


def assemble_brief(
    session: Session, company: Company, event: EarningsEvent, events: Sequence[EarningsEvent]
) -> BriefContent:
    period = (event.fiscal_year, event.fiscal_period)
    end = quarter_ends(company_calendar(session, company)).get(period)
    filing = sections.periodic_filing(session, company.id, end) if end else None
    form = "10-K" if period[1] == "Q4" else "10-Q"
    missing: list[Missing] = []
    table = sections.metric_table(session, company.id, period)
    if table is None:
        reason = f"{form} not yet filed." if filing is None else f"No figures for {label(period)}."
        missing.append(Missing(section="headline_table", reason=reason))
    versus = [row for row in period_guidance(session, company, period) if row.outcome is not None]
    if not versus:
        missing.append(
            Missing(
                section="versus_guidance", reason=f"No company guidance found for {label(period)}."
            )
        )
    reaction = sections.reaction(session, company, filing_id=_filing_id(event))
    if reaction is None or reaction.move is None:
        missing.append(
            Missing(section="reaction", reason="No price data around the earnings 8-K yet.")
        )
        reaction = None
    changed = sections.what_changed(session, filing) if filing else None
    if changed is None:
        reason = f"{form} not yet filed." if filing is None else f"No earlier {form} to compare."
        missing.append(Missing(section="what_changed", reason=reason))
    earlier = [
        e for e in events if e.status == "reported" and (e.fiscal_year, e.fiscal_period) < period
    ]
    since = (
        earlier[0].report_date + timedelta(days=1)
        if earlier and earlier[0].report_date
        else (event.report_date or date.today()) - timedelta(days=OPEN_FLAG_DAYS)
    )
    return BriefContent(
        header=header(company, event),
        headline_table=table,
        versus_guidance=versus,
        reaction=reaction,
        what_changed=changed,
        new_flags=sections.flags_since(session, company, since),
        missing=missing,
    )


def inputs_hash(content: BaseModel) -> str:
    """sha-256 of the assembled content: every input's IDs and values (FR-EB-007)."""
    payload = json.dumps(content.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _sections(content: dict[str, Any]) -> dict[str, str]:
    return {k: json.dumps(v, sort_keys=True) for k, v in content.items() if k not in ("narrative",)}


def inputs_label(kind: Kind, previous: EarningsBrief | None, content: dict[str, Any]) -> str:
    """What this version's inputs add over the previous one, for the version switcher."""
    form = "10-K" if content["header"]["fiscal_period"] == "Q4" else "10-Q"
    if previous is None:
        if kind == "preview":
            return "first preview"
        return f"after {form} filed" if content.get("what_changed") else "after earnings release"
    if kind == "brief" and content.get("what_changed") and not previous.content.get("what_changed"):
        return f"after {form} filed"
    before, after = _sections(previous.content), _sections(content)
    changed = sorted(k for k in after if before.get(k) != after[k] and k != "missing")
    return "updated: " + ", ".join(changed).replace("_", " ") if changed else "updated"


def to_stored(row: EarningsBrief) -> StoredBrief:
    content = row.content
    return StoredBrief(
        id=row.id,
        kind=row.kind,  # type: ignore[arg-type]  # CHECK kind_known
        fiscal_year=row.fiscal_year,
        fiscal_period=row.fiscal_period,
        period_label=label((row.fiscal_year, row.fiscal_period)),
        version=row.version,
        inputs_label=row.inputs_label,
        created_at=row.created_at,
        preview=EarningsPreview.model_validate(content) if row.kind == "preview" else None,
        brief=BriefContent.model_validate(content) if row.kind == "brief" else None,
    )


def _start_of_day() -> datetime:
    return datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC)


def generate(
    session: Session,
    company: Company,
    kind: Kind,
    *,
    llm: LLMClient | None = None,
    settings: Settings | None = None,
    user_id: int | None = None,
    today: date | None = None,
) -> tuple[EarningsBrief, bool]:
    """(stored version, created?) for the company's current quarter of this kind."""
    settings = settings or get_settings()
    today = today or datetime.now(UTC).date()
    if not repo.is_covered(session, company, settings.earnings_brief_seed_tickers):
        raise BriefUnavailable(
            "not_covered", "Briefs are made only for companies on a watchlist or in the seed set."
        )
    events = build_calendar(session, company)
    event = upcoming_event(events) if kind == "preview" else latest_reported(events)
    if event is None:
        raise BriefUnavailable("no_period", f"No quarter to make a {kind} for yet.")
    period = (event.fiscal_year, event.fiscal_period)
    content: EarningsPreview | BriefContent = (
        assemble_preview(session, company, event, today=today)
        if kind == "preview"
        else assemble_brief(session, company, event, events)
    )
    digest = inputs_hash(content)
    stored = repo.find_brief(session, company.id, period, kind, digest)
    if stored is not None:
        return stored, False
    if repo.created_since(session, _start_of_day()) >= settings.earnings_brief_daily_cap:
        log_event(
            logger,
            logging.WARNING,
            "earnings.daily_cap_reached",
            cap=settings.earnings_brief_daily_cap,
            ticker=company.ticker,
            kind=kind,
        )
        raise BriefUnavailable("daily_cap", "Today's brief generation limit has been reached.")
    llm = llm or get_llm_client()
    if isinstance(content, EarningsPreview):
        content.watch_items = watch.reword(
            session, content.watch_items, llm=llm, settings=settings, user_id=user_id
        )
    else:
        content.narrative = narrative.narrative(
            session, content, llm=llm, settings=settings, user_id=user_id
        )
        if content.narrative is None:
            content.missing.append(
                Missing(section="narrative", reason="No summary sentence passed verification.")
            )
    previous = repo.latest_version(session, company.id, period, kind)
    dumped = content.model_dump(mode="json")
    row = repo.add_brief(
        session,
        company_id=company.id,
        fiscal_year=period[0],
        fiscal_period=period[1],
        kind=kind,
        version=(previous.version + 1) if previous else 1,
        inputs_hash=digest,
        inputs_label=inputs_label(kind, previous, dumped),
        report_date_estimated=content.header.date_estimated,
        content=dumped,
        prompt_version=PROMPT_VERSION,
        model=model_label(settings),
    )
    refresh_company_theses(session, company)  # the new brief on theses' timelines (FR-TH-008)
    log_event(
        logger,
        logging.INFO,
        "earnings.brief_stored",
        ticker=company.ticker,
        kind=kind,
        period=label(period),
        version=row.version,
    )
    return row, True


def try_generate(session: Session, company: Company, kind: Kind) -> EarningsBrief | None:
    """`generate` for scheduled callers: an unavailable brief is logged, not raised."""
    try:
        return generate(session, company, kind)[0]
    except BriefUnavailable as exc:
        log_event(
            logger,
            logging.INFO,
            "earnings.brief_skipped",
            ticker=company.ticker,
            kind=kind,
            reason=exc.code,
        )
        return None


def release_ingested(session: Session, company: Company, event: EarningsEvent) -> bool:
    """Both the Item 2.02 8-K and its EX-99.1 (or lone EX-99) press release are stored (7c)."""
    filing_id = _filing_id(event)
    filing = filing_repo.get_filing(session, filing_id) if filing_id else None
    if filing is None:
        return False
    exhibits = filing_repo.exhibit_documents(
        session, company_id=company.id, parent_accession=filing.accession_number
    )
    return any((d.doc_metadata or {}).get("exhibit_type") in ("EX-99.1", "EX-99") for d in exhibits)


def after_filings(session: Session, company: Company) -> EarningsBrief | None:
    """Post-ingest hook (FR-EB-008): a brief once the 8-K and its EX-99.1 are in, and a new
    version when the 10-Q lands (its inputs change). Idempotent: unchanged inputs store nothing."""
    event = latest_reported(build_calendar(session, company))
    if event is None or not release_ingested(session, company, event):
        return None
    return try_generate(session, company, "brief")


def due_previews(session: Session, companies: Sequence[Company], *, today: date) -> int:
    """Previews for scheduled, non-estimated dates within the lead window (FR-EB-008). An
    estimated date never triggers one. Returns previews stored or found."""
    lead = get_settings().earnings_preview_lead_days
    made = 0
    for company in companies:
        event = upcoming_event(build_calendar(session, company))
        if (
            event is None
            or event.status != "scheduled"
            or event.source == "estimated"
            or event.report_date is None
            or not today <= event.report_date <= today + timedelta(days=lead)
        ):
            continue
        made += try_generate(session, company, "preview") is not None
    return made
