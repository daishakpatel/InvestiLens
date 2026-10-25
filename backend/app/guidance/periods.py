"""Guidance period wording -> fiscal period, on the company's fiscal calendar (FR-GD-004c).

"the third quarter of fiscal 2027" -> (2027, "Q3"); "for the full year fiscal 2027" -> (2027,
"FY"). Wording without "fiscal" names a calendar year, which is the fiscal year only for a company
whose fiscal year ends in late December or the first days of January; for NVIDIA (year ending in
late January) "the third quarter of 2027" is ambiguous and is rejected. A resolved period must
also end on or after the release date and within two years of it, by the fiscal calendar's known
period ends (or, for a period not yet in it, by the latest known fiscal year end rolled forward),
so a misread year is caught.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta

Period = tuple[int, str]  # (fiscal_year, "Q1".."Q4" | "FY")

_ORDINAL = {"first": 1, "second": 2, "third": 3, "fourth": 4}
_YEAR = r"(?:(?:fiscal(?:\s+year)?|fy)\s*'?\s*)?(?P<year>\d{4}|\d{2})(?!\d)"
_PATTERNS = (
    # "third quarter of fiscal 2027", "fourth-quarter 2026", "third quarter" (no year)
    re.compile(
        r"\b(?P<q>first|second|third|fourth)[\s-]+(?:fiscal[\s-]+)?quarter\b"
        rf"(?:,?\s+(?:of\s+)?(?:the\s+)?{_YEAR})?",
        re.I,
    ),
    re.compile(rf"\bq(?P<q>[1-4])(?!\d)[\s-]*(?:{_YEAR})?", re.I),  # "Q3 FY2027", "Q3 fiscal 2027"
    # "full year fiscal 2027", "fiscal year 2027", "full-year 2026"
    re.compile(rf"\b(?:full[\s-]+year|fiscal[\s-]+year|year)\s+(?:of\s+)?{_YEAR}", re.I),
    re.compile(rf"\b{_YEAR}", re.I),  # "fiscal 2027", "FY27" (a bare number needs "fiscal")
    re.compile(r"\b(?:for|in)\s+(?:calendar\s+)?(?P<year>20\d{2})\b", re.I),  # "for 2027"
)
_FISCAL = re.compile(r"fiscal|\bfy|q[1-4]\s*fy", re.I)
_FAR = timedelta(days=730)
_QUARTER = timedelta(weeks=13)


@dataclass(frozen=True)
class Mention:
    start: int
    year: int | None
    quarter: int | None
    fiscal: bool  # the wording said "fiscal" / "FY"


@dataclass(frozen=True)
class CompanyCalendar:
    """What the company's fiscal calendar tells us. `known_ends` holds the period ends recorded
    in `fiscal_calendars`; `anchor` is the latest known fiscal year (label, end date)."""

    calendar_aligned: bool  # fiscal year == calendar year, so "2027" needs no "fiscal"
    anchor: tuple[int, date] | None = None
    known_ends: Mapping[Period, date] = field(default_factory=dict)

    def period_end(self, period: Period) -> date | None:
        if period in self.known_ends:
            return self.known_ends[period]
        if self.anchor is None:
            return None
        anchor_year, anchor_end = self.anchor
        year = anchor_end.year + period[0] - anchor_year
        end = date(year, anchor_end.month, min(anchor_end.day, 28))
        quarter = 4 if period[1] == "FY" else int(period[1][1])
        return end - _QUARTER * (4 - quarter)


def is_calendar_aligned(year_end: date | None, fiscal_year_end: str | None) -> bool:
    """A fiscal year ending in December or in the first week of January is the calendar year.
    `fiscal_year_end` is the companies column ("MM-DD"), used when the calendar has no year."""
    if year_end is not None:
        month, day = year_end.month, year_end.day
    elif fiscal_year_end and re.fullmatch(r"\d{2}-\d{2}", fiscal_year_end):
        month, day = int(fiscal_year_end[:2]), int(fiscal_year_end[3:])
    else:
        return False
    return month == 12 or (month == 1 and day <= 7)


def mentions(text: str) -> list[Mention]:
    """Every period phrase in `text`, in order. A span claimed by an earlier pattern (a quarter
    phrase) is not read again by a later one (its bare "fiscal 2027")."""
    found: list[Mention] = []
    taken: list[tuple[int, int]] = []
    for pattern in _PATTERNS:
        for m in pattern.finditer(text):
            if any(s < m.end() and m.start() < e for s, e in taken):
                continue
            fiscal = bool(_FISCAL.search(m.group(0)))
            raw_year, q = m.groupdict().get("year"), m.groupdict().get("q")
            if pattern is _PATTERNS[3] and not fiscal:
                continue  # a bare number is not a period
            year = None if raw_year is None else int(raw_year)
            if year is not None and year < 100:
                year = 2000 + year if fiscal else None  # "FY27"; a bare "27" is no year
            quarter = None if q is None else (int(q) if q.isdigit() else _ORDINAL[q.lower()])
            taken.append((m.start(), m.end()))
            found.append(Mention(m.start(), year, quarter, fiscal))
    return sorted(found, key=lambda m: m.start)


def resolve(mention: Mention, calendar: CompanyCalendar) -> Period | None:
    """The fiscal period a phrase names, or None when it names none unambiguously."""
    if mention.year is None:
        return None  # "the third quarter": which year?
    if not mention.fiscal and not calendar.calendar_aligned:
        return None  # "2027" for a non-calendar fiscal year: calendar or fiscal 2027?
    return (mention.year, "FY" if mention.quarter is None else f"Q{mention.quarter}")


def resolve_text(text: str, calendar: CompanyCalendar) -> Period | None:
    """The single period `text` names; None if it names none, or more than one."""
    found = {resolve(m, calendar) for m in mentions(text)}
    return found.pop() if len(found) == 1 else None


def item_period(
    quote: str, preceding: str, calendar: CompanyCalendar
) -> tuple[Period | None, str | None]:
    """(period, None) or (None, reason) for a guidance quote. The quote's own wording wins;
    otherwise the nearest period phrase before it in the outlook ("NVIDIA's outlook for the third
    quarter of fiscal 2027 is as follows:" above a bullet) applies."""
    own = mentions(quote)
    if own:
        period = resolve_text(quote, calendar)
        return (period, None) if period else (None, "ambiguous_period")
    before = mentions(preceding)
    if not before:
        return None, "no_period"
    period = resolve(before[-1], calendar)
    return (period, None) if period else (None, "ambiguous_period")


def is_forward(period: Period, issued: date, calendar: CompanyCalendar) -> bool:
    """Guidance is about a period that has not ended when it is issued, and not years away."""
    end = calendar.period_end(period)
    return end is not None and issued <= end <= issued + _FAR
