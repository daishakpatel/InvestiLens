"""Small calendar-date helpers (no third-party dependency)."""

from __future__ import annotations

from datetime import date


def _safe(year: int, month: int, day: int) -> date:
    while True:
        try:
            return date(year, month, day)
        except ValueError:
            day -= 1  # clamp e.g. Feb 30 -> Feb 28


def years_ago(anchor: date, years: int) -> date:
    return _safe(anchor.year - years, anchor.month, anchor.day)


def months_ago(anchor: date, months: int) -> date:
    total = (anchor.year * 12 + (anchor.month - 1)) - months
    return _safe(total // 12, total % 12 + 1, anchor.day)
