"""Per-share figures and share counts restated to today's share basis (DR-026, ADR-0051).

A filing reports per-share figures on the share basis of the day it was filed: NVIDIA's FY2024
10-K (filed Feb 2024) gives diluted EPS of $11.93, before the 10-for-1 split of June 2024, while
its FY2025 10-K gives $2.94 after it. Comparing periods needs one basis, so a figure is divided
(and a share count multiplied) by every split that took effect after it was filed. Stored rows
stay as reported, so a citation still matches its filing; the adjustment is applied when a
series is served, and its formula text says what was done.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.finance.valuation_builder import load_splits, split_factor
from app.models import FinancialFact

SPLIT_TAG = "us-gaap:StockholdersEquityNoteStockSplitConversionRatio1"
PER_SHARE_UNIT = "USD/shares"
SHARES_UNIT = "shares"
# Filings tag one split under several contexts (approval date, quarter end) up to a few weeks apart.
_SAME_SPLIT = timedelta(days=120)

Split = tuple[date, Decimal]  # (effective date, ratio): 10 for a 10-for-1, 0.1 for a 1-for-10


def merge_splits(priced: Sequence[Split], tagged: Sequence[Split]) -> list[Split]:
    """One entry per split, from the price feed and the company's own split tags.

    The price feed's ex-dates are exact but only reach back `backfill_price_years`; the filing
    tags cover every split since XBRL began but are dated by their context. A tagged split with
    the same ratio as a priced one nearby is that split; otherwise the latest date it was tagged
    under stands in for its ex-date (shortcut: off by days at most, which only matters for a
    filing made between a split's approval and its ex-date).
    """
    splits = [(when, ratio, True) for when, ratio in priced]
    for when, ratio in sorted(tagged):
        if ratio <= 0 or ratio == 1:
            continue
        same = next(
            (
                i
                for i, (d, r, _) in enumerate(splits)
                if r == ratio and abs(d - when) <= _SAME_SPLIT
            ),
            None,
        )
        if same is None:
            splits.append((when, ratio, False))
        elif not splits[same][2]:  # a tag-only split moves to its latest tagged date
            splits[same] = (max(splits[same][0], when), ratio, False)
    return sorted((when, ratio) for when, ratio, _ in splits)


def company_splits(session: Session, company_id: int) -> list[Split]:
    tagged = session.execute(
        select(FinancialFact.period_end, FinancialFact.value).where(
            FinancialFact.company_id == company_id, FinancialFact.concept_tag == SPLIT_TAG
        )
    ).all()
    return merge_splits(
        load_splits(session, company_id),
        [(d, Decimal(v)) for d, v in tagged if d is not None and v is not None],
    )


def filed_dates(session: Session, company_id: int, accessions: Iterable[str]) -> dict[str, date]:
    """When each filing was filed, from the facts it reported."""
    wanted = set(accessions)
    if not wanted:
        return {}
    rows = session.execute(
        select(FinancialFact.accession_number, func.min(FinancialFact.filed_date))
        .where(FinancialFact.company_id == company_id, FinancialFact.accession_number.in_(wanted))
        .group_by(FinancialFact.accession_number)
    ).all()
    return {acc: filed for acc, filed in rows if filed is not None}


@dataclass(frozen=True)
class Restated:
    value: Decimal
    note: str | None  # None when no split followed the filing


def restate(value: Decimal, unit: str, filed: date | None, splits: Sequence[Split]) -> Restated:
    """`value` on today's share basis. Units other than per-share and shares pass through, as
    does a figure whose filing date is unknown (it cannot be placed against the splits)."""
    if unit not in (PER_SHARE_UNIT, SHARES_UNIT) or filed is None:
        return Restated(value, None)
    factor = split_factor(splits, filed, date.max)
    if factor == 1:
        return Restated(value, None)
    later = ", ".join(f"{_ratio(r)} on {d.isoformat()}" for d, r in splits if d > filed)
    per_share = unit == PER_SHARE_UNIT
    op = "divided" if per_share else "multiplied"
    return Restated(
        value / factor if per_share else value * factor,
        f"Split-adjusted: as filed {_plain(value)}, {op} by {_plain(factor)} for later stock "
        f"splits ({later})",
    )


def _plain(n: Decimal) -> str:
    return f"{n.normalize():,f}"


def _ratio(r: Decimal) -> str:
    return f"{_plain(r)}-for-1" if r >= 1 else f"1-for-{_plain(1 / r)}"
