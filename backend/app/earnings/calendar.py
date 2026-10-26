"""Earnings calendar: when each fiscal quarter was, or will be, reported (FR-EB-001/002).

A date comes from, in order:

1. an Item 2.02 8-K already filed (`sec_8k`, status `reported`): the 8-K list is the reaction
   code's (`filings.earnings.earnings_filings`), and the quarter is the latest fiscal quarter that
   ended before the filing date on the company's fiscal calendar;
2. the company's own statement of a future date in an 8-K or press release (`announcement`): one
   sentence that names the quarter, a "will report/host/…" verb and exactly one date later than
   the document, matched by a strict regex and kept as a quote;
3. an estimate (`estimated`): the same quarter's report date a year earlier plus 52 weeks, which
   keeps the weekday. It is shown as "~" and never notifies on its own.

Only the quarter after the latest reported one is looked ahead to. A quarter with neither a
statement nor a year-ago date is `unknown`.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.filings.earnings import earnings_filings
from app.guidance import periods
from app.guidance.extract import company_calendar
from app.models import Company, DocumentChunk, EarningsEvent
from app.repositories import earnings as repo

Period = tuple[int, str]  # (fiscal_year, "Q1".."Q4")

REPORT_LAG = timedelta(days=100)  # a quarter is reported within ~100 days of its end
ESTIMATE_SHIFT = timedelta(weeks=52)  # same weekday a year on
_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
_DATE = re.compile(
    rf"\b(?:(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day,\s+)?(?P<month>{_MONTHS})\s+"
    r"(?P<day>\d{1,2}),\s+(?P<year>20\d{2})\b"
)
_ANNOUNCES = re.compile(
    r"\b(?:will|plans to|intends to)\s+(?:report|announce|release|host|hold|conduct|webcast)\b",
    re.I,
)
_AFTER_CLOSE = re.compile(
    r"\bafter\s+(?:the\s+)?(?:u\.s\.\s+)?(?:stock\s+)?market(?:s)?\s+clos", re.I
)
_BEFORE_OPEN = re.compile(
    r"\bbefore\s+(?:the\s+)?(?:u\.s\.\s+)?(?:stock\s+)?market(?:s)?\s+open", re.I
)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
CHUNK_PREFILTER = "%quarter%"


def label(period: Period) -> str:
    return f"{period[1]} FY{period[0]}"


def next_period(period: Period) -> Period:
    year, quarter = period[0], int(period[1][1])
    return (year, f"Q{quarter + 1}") if quarter < 4 else (year + 1, "Q1")


def previous_period(period: Period) -> Period:
    year, quarter = period[0], int(period[1][1])
    return (year, f"Q{quarter - 1}") if quarter > 1 else (year - 1, "Q4")


def year_ago(period: Period) -> Period:
    return (period[0] - 1, period[1])


def quarter_ends(calendar: periods.CompanyCalendar) -> dict[Period, date]:
    """Each fiscal quarter's end: the calendar's known ends (a fiscal year end is its Q4), plus the
    next four quarters projected from the latest known fiscal year."""
    ends = {
        (year, "Q4" if part == "FY" else part): end
        for (year, part), end in calendar.known_ends.items()
    }
    if ends:
        period = max(ends)
        for _ in range(4):
            period = next_period(period)
            end = calendar.period_end(period)
            if end is not None:
                ends.setdefault(period, end)
    return ends


def reported_period(day: date, ends: dict[Period, date]) -> Period | None:
    """The quarter an earnings release on `day` reports: the latest one ended before it."""
    ended = [(end, period) for period, end in ends.items() if end < day <= end + REPORT_LAG]
    return max(ended)[1] if ended else None


def _date(match: re.Match[str]) -> date | None:
    try:
        return datetime.strptime(
            f"{match['month']} {match['day']} {match['year']}", "%B %d %Y"
        ).date()
    except ValueError:
        return None


def announced(
    chunks: Sequence[DocumentChunk], period: Period, calendar: periods.CompanyCalendar
) -> tuple[date, str, str, DocumentChunk] | None:
    """(date, report_time, sentence, chunk) of the newest statement of `period`'s future report
    date, or None. A sentence counts only when it names exactly that quarter, a "will report"-type
    verb and exactly one date later than its own document."""
    for chunk in chunks:  # newest first
        for sentence in _SENTENCE.split(chunk.text):
            if not _ANNOUNCES.search(sentence):
                continue
            dates = list(_DATE.finditer(sentence))
            if len(dates) != 1 or periods.resolve_text(sentence, calendar) != period:
                continue
            day = _date(dates[0])
            if day is None or chunk.filing_date is None or day <= chunk.filing_date:
                continue
            time = (
                "amc"
                if _AFTER_CLOSE.search(sentence)
                else "bmo"
                if _BEFORE_OPEN.search(sentence)
                else "unknown"
            )
            return day, time, sentence.strip(), chunk
    return None


def _row(company_id: int, period: Period, **values: Any) -> dict[str, Any]:
    return {
        "company_id": company_id,
        "fiscal_year": period[0],
        "fiscal_period": period[1],
        "report_time": "unknown",
        "source_id": None,
        "quote": None,
        **values,
    }


def build_calendar(session: Session, company: Company) -> list[EarningsEvent]:
    """Refresh the company's events from stored filings and return them, newest first.
    Idempotent: one row per quarter, replaced on each run."""
    calendar = company_calendar(session, company)
    ends = quarter_ends(calendar)
    rows: dict[Period, dict[str, Any]] = {}
    for filing in earnings_filings(session, company_id=company.id):  # oldest first
        day = filing.filing_date
        period = reported_period(day, ends) if day else None
        if period is not None and period not in rows:  # a second 8-K for a quarter is not news
            rows[period] = _row(
                company.id,
                period,
                report_date=day,
                source="sec_8k",
                status="reported",
                source_id=f"filing:{filing.id}",
            )
    if rows:
        last = max(rows)
        upcoming = next_period(last)
        chunks = repo.announcement_chunks(
            session, company.id, after=rows[last]["report_date"], like=CHUNK_PREFILTER
        )
        found = announced(chunks, upcoming, calendar)
        prior = rows.get(year_ago(upcoming))
        if found is not None:
            day, time, sentence, chunk = found
            rows[upcoming] = _row(
                company.id,
                upcoming,
                report_date=day,
                report_time=time,
                source="announcement",
                status="scheduled",
                source_id=chunk.paragraph_id,
                quote=sentence,
            )
        elif prior is not None:
            rows[upcoming] = _row(
                company.id,
                upcoming,
                report_date=prior["report_date"] + ESTIMATE_SHIFT,
                source="estimated",
                status="scheduled",
            )
        else:
            rows[upcoming] = _row(
                company.id, upcoming, report_date=None, source="estimated", status="unknown"
            )
    repo.upsert_events(session, list(rows.values()))
    return repo.events(session, company.id)


def upcoming_event(events: Sequence[EarningsEvent]) -> EarningsEvent | None:
    """The newest quarter not yet reported (`events` newest first)."""
    latest = events[0] if events else None
    return latest if latest is not None and latest.status != "reported" else None


def latest_reported(events: Sequence[EarningsEvent]) -> EarningsEvent | None:
    return next((e for e in events if e.status == "reported"), None)
