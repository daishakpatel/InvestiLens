"""Earnings-day price reaction (§37.3): a deterministic move around each earnings 8-K.

An earnings release is an 8-K carrying Item 2.02 (Results of Operations). The filing does not say
whether it landed before the open or after the close, so the reaction is measured across both
possibilities: from the last close strictly before the filing date to the first close strictly
after it. Adjusted closes keep the move continuous across splits (DR-025).

Phase 7j adds, from the same bars: the move at the first session's open (its open adjusted by
that day's close-to-adjusted-close factor), the 5-session move, and that session's volume over the
average of the 20 sessions before the filing (`volume_ratio`, None without volume data).
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Filing, PriceHistory
from app.repositories import filings as filing_repo
from app.repositories import prices as price_repo

EARNINGS_ITEM = "2.02"
_WINDOW = timedelta(days=10)  # calendar slack to find a session on each side of the date
_LOOKBACK = timedelta(days=40)  # enough calendar days for 20 sessions of average volume
_FIVE_DAY = 5
_VOLUME_SESSIONS = 20
_RATIO = Decimal("0.000001")


@dataclass(frozen=True)
class EarningsReaction:
    filing: Filing
    pre_date: date | None = None
    pre_close: Decimal | None = None
    post_date: date | None = None
    post_close: Decimal | None = None
    move: Decimal | None = None  # ratio: 0.05 = +5%
    reason: str | None = None  # set when `move` is None
    move_at_open: Decimal | None = None
    move_5d: Decimal | None = None
    volume_ratio: Decimal | None = None


def price_move(pre_close: Decimal, post_close: Decimal) -> Decimal:
    return ((post_close - pre_close) / pre_close).quantize(_RATIO)


def earnings_filings(session: Session, *, company_id: int) -> list[Filing]:
    """The company's earnings 8-Ks (Item 2.02), oldest first."""
    return [
        f
        for f in filing_repo.list_filings_by_type(session, company_id=company_id, filing_type="8-K")
        if f.filing_date is not None and EARNINGS_ITEM in (f.items or [])
    ]


def _open_move(bar: PriceHistory, pre_close: Decimal) -> Decimal | None:
    if bar.open is None or not bar.close or bar.adj_close is None:
        return None
    return price_move(pre_close, bar.open * bar.adj_close / bar.close)


def _volume_ratio(bars: list[PriceHistory], before: int, after: int) -> Decimal | None:
    window = [b.volume for b in bars[max(0, before + 1 - _VOLUME_SESSIONS) : before + 1]]
    volume = bars[after].volume
    if volume is None or len(window) < _VOLUME_SESSIONS or any(v is None for v in window):
        return None
    average = Decimal(sum(v for v in window if v is not None)) / len(window)
    return (Decimal(volume) / average).quantize(_RATIO) if average else None


def earnings_reactions(session: Session, *, company_id: int) -> list[EarningsReaction]:
    """Price reaction for each of the company's earnings 8-Ks, newest first."""
    filings = earnings_filings(session, company_id=company_id)
    if not filings:
        return []
    dates = [f.filing_date for f in filings if f.filing_date is not None]
    bars = [
        bar
        for bar in price_repo.get_price_history(
            session, company_id=company_id, start=min(dates) - _LOOKBACK, end=max(dates) + _WINDOW
        )
        if bar.adj_close is not None
    ]
    sessions = [bar.date for bar in bars]
    out: list[EarningsReaction] = []
    for filing, day in zip(reversed(filings), reversed(dates), strict=True):
        before = bisect_left(sessions, day) - 1
        after = bisect_right(sessions, day)
        if before < 0 or after >= len(bars) or day - sessions[before] > _WINDOW:
            out.append(EarningsReaction(filing, reason="NO_PRICE_DATA"))
            continue
        pre, post = bars[before], bars[after]
        pre_close, post_close = pre.adj_close, post.adj_close
        if not pre_close or post_close is None or post.date - day > _WINDOW:
            out.append(EarningsReaction(filing, reason="NO_PRICE_DATA"))
            continue
        fifth = after + _FIVE_DAY - 1
        fifth_close = bars[fifth].adj_close if fifth < len(bars) else None
        out.append(
            EarningsReaction(
                filing,
                pre.date,
                pre_close,
                post.date,
                post_close,
                price_move(pre_close, post_close),
                move_at_open=_open_move(post, pre_close),
                move_5d=price_move(pre_close, fifth_close) if fifth_close is not None else None,
                volume_ratio=_volume_ratio(bars, before, after),
            )
        )
    return out
