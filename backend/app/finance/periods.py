"""Period classification and fiscal-calendar derivation (DR-021).

Facts carry raw period_start/period_end; this module turns them into fiscal periods. Fiscal year
is kept separate from calendar dates — e.g. NVIDIA's FY ends the last Sunday of January, so
FY2026 ends 2026-01-25, not 2025-12-31.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# Duration windows (days) used to classify a flow fact's period.
FULL_YEAR = (350, 380)
QUARTER = (80, 100)


def duration_days(start: date | None, end: date | None) -> int | None:
    if start is None or end is None:
        return None
    return (end - start).days + 1  # inclusive


def is_full_year(start: date | None, end: date | None) -> bool:
    days = duration_days(start, end)
    return days is not None and FULL_YEAR[0] <= days <= FULL_YEAR[1]


def is_quarter(start: date | None, end: date | None) -> bool:
    days = duration_days(start, end)
    return days is not None and QUARTER[0] <= days <= QUARTER[1]


def fiscal_year_of(period_end: date, fye_month: int = 12) -> int:
    """Fiscal year a period belongs to, given the company's fiscal-year-end month (DR-021).

    A period ending in month <= FYE month belongs to that calendar year's fiscal year; a period
    ending after it belongs to the next. For a Jan FYE (NVIDIA), a quarter ending in April 2025
    is part of FY2026. For a December FYE this reduces to the calendar year.
    """
    return period_end.year if period_end.month <= fye_month else period_end.year + 1


@dataclass(frozen=True)
class FiscalPeriod:
    fiscal_year: int
    fiscal_quarter: int | None  # None = full year
    period_start: date
    period_end: date
    period_type: str  # FY | Q
    weeks_in_period: int


def _weeks(start: date, end: date) -> int:
    return round(((end - start).days + 1) / 7)


def derive_fiscal_calendar(
    annual: list[tuple[date, date]], quarterly: list[tuple[date, date]], fye_month: int = 12
) -> list[FiscalPeriod]:
    """Build fiscal-calendar rows from annual and quarterly (start, end) spans.

    Quarter numbers are assigned by ordering within each fiscal year (DR-021). 52/53-week
    handling falls out of `weeks_in_period` computed from the actual span.
    """
    periods: list[FiscalPeriod] = []
    for start, end in annual:
        periods.append(
            FiscalPeriod(fiscal_year_of(end, fye_month), None, start, end, "FY", _weeks(start, end))
        )

    by_year: dict[int, list[tuple[date, date]]] = {}
    for start, end in quarterly:
        by_year.setdefault(fiscal_year_of(end, fye_month), []).append((start, end))
    for fiscal_year, spans in by_year.items():
        for index, (start, end) in enumerate(sorted(spans, key=lambda s: s[1]), start=1):
            if index > 4:
                break
            periods.append(FiscalPeriod(fiscal_year, index, start, end, "Q", _weeks(start, end)))
    return periods
