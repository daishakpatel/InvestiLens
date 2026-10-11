"""Earnings-day price reaction (§37.3): a deterministic move around each earnings 8-K.

An earnings release is an 8-K carrying Item 2.02 (Results of Operations). The filing does not say
whether it landed before the open or after the close, so the reaction is measured across both
possibilities: from the last close strictly before the filing date to the first close strictly
after it. Adjusted closes keep the move continuous across splits (DR-025).
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Filing
from app.repositories import filings as filing_repo
from app.repositories import prices as price_repo

EARNINGS_ITEM = "2.02"
_WINDOW = timedelta(days=10)  # calendar slack to find a session on each side of the date


@dataclass(frozen=True)
class EarningsReaction:
    filing: Filing
    pre_date: date | None = None
    pre_close: Decimal | None = None
    post_date: date | None = None
    post_close: Decimal | None = None
    move: Decimal | None = None  # ratio: 0.05 = +5%
    reason: str | None = None  # set when `move` is None


def price_move(pre_close: Decimal, post_close: Decimal) -> Decimal:
    return ((post_close - pre_close) / pre_close).quantize(Decimal("0.000001"))


def earnings_reactions(session: Session, *, company_id: int) -> list[EarningsReaction]:
    """Price reaction for each of the company's earnings 8-Ks, newest first."""
    filings = [
        f
        for f in filing_repo.list_filings_by_type(session, company_id=company_id, filing_type="8-K")
        if f.filing_date is not None and EARNINGS_ITEM in (f.items or [])
    ]
    if not filings:
        return []
    dates = [f.filing_date for f in filings if f.filing_date is not None]
    bars = [
        (bar.date, bar.adj_close)
        for bar in price_repo.get_price_history(
            session, company_id=company_id, start=min(dates) - _WINDOW, end=max(dates) + _WINDOW
        )
        if bar.adj_close is not None
    ]
    sessions = [d for d, _ in bars]
    out: list[EarningsReaction] = []
    for filing, day in zip(reversed(filings), reversed(dates), strict=True):
        before = bisect_left(sessions, day) - 1
        after = bisect_right(sessions, day)
        if before < 0 or after >= len(bars) or day - sessions[before] > _WINDOW:
            out.append(EarningsReaction(filing, reason="NO_PRICE_DATA"))
            continue
        (pre_date, pre_close), (post_date, post_close) = bars[before], bars[after]
        if pre_close == 0 or post_date - day > _WINDOW:
            out.append(EarningsReaction(filing, reason="NO_PRICE_DATA"))
            continue
        out.append(
            EarningsReaction(
                filing,
                pre_date,
                pre_close,
                post_date,
                post_close,
                price_move(pre_close, post_close),
            )
        )
    return out
