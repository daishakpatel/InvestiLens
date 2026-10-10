"""Calendarization: align companies with different fiscal-year ends onto a common period (§37.1).

Fiscal periods are stored separately from calendar dates (DR-021), so NVIDIA's FY2025 (ending
January 2025) must not be compared naively against a December-year peer's FY2024. We map each
fiscal period to the *calendar year it predominantly represents* and compare within that.

Base metric rows carry an exact `period_end`; derived-ratio rows do not (they inherit the fiscal
period only), so the mapping falls back to the fiscal year plus the company's fiscal-year-end month
— which agrees with the date-based result for the base rows of the same period.
"""

from __future__ import annotations

from datetime import date

from app.models import Company, FinancialMetric

# A fiscal year ending in these months falls mostly in the PRIOR calendar year (a Jan-May FYE
# means the period spanned the previous year). This is the common "calendar year" convention used
# to line up off-cycle fiscal years (e.g. NVIDIA, FYE late January) with December-year peers.
_PRIOR_YEAR_FYE_MAX_MONTH = 5


def calendar_year(period_end: date) -> int:
    """Map a fiscal period-end date to the calendar year it predominantly represents.

    NVIDIA FY2026 ends ~2026-01-25 but spans Feb 2025-Jan 2026 -> CY2025, aligning it with AMD/Intel
    whose FY2025 ends in December 2025 -> CY2025.
    """
    if period_end.month <= _PRIOR_YEAR_FYE_MAX_MONTH:
        return period_end.year - 1
    return period_end.year


def fiscal_year_end_month(company: Company) -> int | None:
    """Parse the company's "MM-DD" fiscal-year end into a month number, or None if unknown."""
    fye = company.fiscal_year_end
    if fye and "-" in fye:
        head = fye.split("-", 1)[0]
        if head.isdigit():
            return int(head)
    return None


def row_calendar_year(row: FinancialMetric, fye_month: int | None) -> int | None:
    """Calendar year for one metric row: exact date when present, else fiscal year + FYE month."""
    if row.period_end is not None:
        return calendar_year(row.period_end)
    if row.fiscal_year is None:
        return None
    if fye_month is not None:
        return row.fiscal_year - 1 if fye_month <= _PRIOR_YEAR_FYE_MAX_MONTH else row.fiscal_year
    return row.fiscal_year  # last resort: assume a calendar-year (December) issuer


def calendarized(
    metrics: list[FinancialMetric], fye_month: int | None
) -> dict[int, FinancialMetric]:
    """Index a company's FY metric rows by calendar year (later fiscal year wins a collision)."""
    by_year: dict[int, FinancialMetric] = {}
    for m in metrics:
        cy = row_calendar_year(m, fye_month)
        if cy is None:
            continue
        existing = by_year.get(cy)
        if existing is None or (m.fiscal_year or 0) > (existing.fiscal_year or 0):
            by_year[cy] = m
    return by_year


def latest_common_year(per_company_years: list[set[int]]) -> int | None:
    """The most recent calendar year for which every company has a calendarized data point."""
    if not per_company_years:
        return None
    common = set.intersection(*per_company_years)
    return max(common) if common else None
