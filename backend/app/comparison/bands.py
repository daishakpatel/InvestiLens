"""Valuation bands: today's multiple within its own history and within its peers (Phase 7h,
FR-PS-009..013, ADR-0046).

Reads `valuation_history` (built by `finance.valuation_history`). For each multiple:

- own: today's value among the last five fiscal-year-end values and today's (`percentile_rank`),
  with min / median / max; needs five usable values for a percentile and three fiscal year ends
  for a band at all ("insufficient history");
- peers: the peer median, today's percentile among peers, and the premium to that median; needs
  three usable peers. Peer values are each company's TTM multiple at its own latest close, so
  different fiscal year ends are already on one calendar basis (DR-PS-002); a peer without one
  (fewer than four quarters, a loss, no prices) is listed as excluded with the reason.

Only `ok` values enter any statistic; `not_meaningful` (a loss, negative EBITDA) never does. Every
label is positional ("in the top quartile of its 5-year range", "18% above peer median"): no
wording judges value, and the advice guard checks every template (FR-PS-011).
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from statistics import median

from sqlalchemy.orm import Session

from app.config import get_settings
from app.finance import point_in_time as pit
from app.finance.metrics import percentile_rank
from app.finance.valuation_history import CURRENT, FISCAL_YEAR_END
from app.models import Company, PeerSet, ValuationHistory
from app.repositories import peers as peer_repo
from app.schemas.peers import (
    ExcludedPeer,
    HistoryPoint,
    OwnBand,
    PeerBand,
    PeerMember,
    PeerSetOut,
    ValuationBand,
    ValuationBandsResponse,
)

OWN_MIN_POINTS = 5  # five fiscal year ends + today; a percentile of fewer is noise
OWN_MIN_YEARS = 3  # fiscal year ends needed to draw a band at all
PEER_MIN = 3  # DR-PS-001

STATUS_REASONS = {
    pit.NOT_MEANINGFUL: "Not meaningful: earnings, EBITDA, cash flow or book value is zero or "
    "negative.",
    pit.MISSING_INPUT: "Not available: a price, share count or four quarters of figures is "
    "missing.",
    pit.NOT_APPLICABLE: "Not applicable to this sector.",
}


def position_label(percentile: Decimal) -> str:
    """Where today sits in its own range, in words that describe position only."""
    if percentile >= Decimal("0.75"):
        return "in the top quartile of its 5-year range"
    if percentile <= Decimal("0.25"):
        return "in the bottom quartile of its 5-year range"
    return "in the middle half of its 5-year range"


def premium_label(premium: Decimal) -> str:
    if abs(premium) < Decimal("0.005"):
        return "in line with the peer median"
    direction = "above" if premium > 0 else "below"
    return f"{abs(premium) * 100:.0f}% {direction} peer median"


def own_band(today: Decimal | None, year_ends: Sequence[Decimal]) -> OwnBand:
    """The band from the usable fiscal-year-end values and today's (FR-PS-009/010)."""
    points = [*year_ends, *([today] if today is not None else [])]
    n = len(points)
    if len(year_ends) < OWN_MIN_YEARS:
        return OwnBand(
            n=n,
            reason=f"Insufficient history: {len(year_ends)} fiscal year ends with a value "
            f"({OWN_MIN_YEARS} needed for a band).",
        )
    band = OwnBand(n=n, min=min(points), median=median(points), max=max(points))
    if today is None:
        band.reason = "No value today, so no position in the range."
    elif n < OWN_MIN_POINTS:
        band.reason = f"A percentile needs {OWN_MIN_POINTS} values; {n} are available."
    else:
        band.percentile = percentile_rank(today, points).value
        band.label = position_label(band.percentile) if band.percentile is not None else None
    return band


def peer_band(
    today: Decimal | None,
    peers: Sequence[tuple[str, ValuationHistory | None]],
    *,
    insufficient_set: bool,
) -> PeerBand:
    """Today's value against each peer's own latest value (FR-PS-009/010)."""
    usable: list[Decimal] = []
    excluded: list[ExcludedPeer] = []
    for ticker, row in peers:
        if row is None:
            excluded.append(ExcludedPeer(ticker=ticker, reason="No valuation yet (no prices)."))
        elif row.status != pit.OK or row.value is None:
            excluded.append(ExcludedPeer(ticker=ticker, reason=STATUS_REASONS[row.status]))
        else:
            usable.append(row.value)
    band = PeerBand(n=len(usable), excluded=excluded)
    if insufficient_set:
        band.reason = "Insufficient peers: the peer set has fewer than three companies."
    elif len(usable) < PEER_MIN:
        band.reason = f"Peer statistics need {PEER_MIN} peers with a value; {len(usable)} have one."
    else:
        band.median = median(usable)
        if today is not None:
            band.percentile = percentile_rank(today, usable).value
            if band.median > 0:
                band.premium_to_peer_median = today / band.median - 1
                band.label = premium_label(band.premium_to_peer_median)
        else:
            band.reason = "No value today to compare with the peers."
    return band


def peer_set_out(session: Session, sets: Sequence[PeerSet]) -> list[PeerSetOut]:
    rows = peer_repo.members(session, [s.id for s in sets])
    settings = get_settings()
    out = []
    for peer_set in sets:
        members = [
            PeerMember(ticker=company.ticker, name=company.name, rationale=member.rationale)
            for member, company in rows
            if member.peer_set_id == peer_set.id
        ]
        insufficient = len(members) < PEER_MIN
        reason = None
        if insufficient and peer_set.kind == peer_repo.SYSTEM_DEFAULT:
            who = (
                "other company in Assay Desk shares"
                if len(members) == 1
                else ("other companies in Assay Desk share")
            )
            reason = (
                f"Insufficient peers: {len(members)} {who} this SIC "
                f"code with a market cap within {settings.peer_market_cap_band_low:g}x-"
                f"{settings.peer_market_cap_band_high:g}x of this company's. Choose peers in a "
                "set of your own."
            )
        out.append(
            PeerSetOut(
                id=peer_set.id,
                name=peer_set.name,
                kind=peer_set.kind,  # type: ignore[arg-type]
                members=members,
                insufficient=insufficient,
                reason=reason,
            )
        )
    return out


def valuation_bands(
    session: Session, company: Company, peer_set: PeerSet | None
) -> ValuationBandsResponse:
    """Every multiple's band for `company` against `peer_set` (default: its system default)."""
    peer_set = peer_set or peer_repo.default_set(session, company.id)
    set_out = peer_set_out(session, [peer_set])[0] if peer_set else None
    peers = (
        [(m.peer_company_id, c.ticker) for m, c in peer_repo.members(session, [peer_set.id])]
        if peer_set
        else []
    )
    rows = peer_repo.history(session, [company.id, *(cid for cid, _ in peers)])
    own = [r for r in rows if r.company_id == company.id]
    current = {r.multiple: r for r in own if r.kind == CURRENT}
    peer_current = {(r.company_id, r.multiple): r for r in rows if r.kind == CURRENT}
    bands = []
    for multiple in pit.MULTIPLES:
        history = [r for r in own if r.multiple == multiple]
        today = current.get(multiple)
        value = today.value if today and today.status == pit.OK else None
        year_ends = [
            r.value
            for r in history
            if r.kind == FISCAL_YEAR_END and r.status == pit.OK and r.value is not None
        ]
        status = today.status if today else pit.MISSING_INPUT
        bands.append(
            ValuationBand(
                multiple=multiple,
                unit="ratio" if multiple in pit.YIELDS else "x",
                status=status,
                value=value,
                reason=None if value is not None else STATUS_REASONS.get(status),
                own=own_band(value, year_ends),
                peers=peer_band(
                    value,
                    [(ticker, peer_current.get((cid, multiple))) for cid, ticker in peers],
                    insufficient_set=set_out is None or set_out.insufficient,
                ),
                history=[
                    HistoryPoint(
                        as_of=r.as_of_date,
                        kind=r.kind,  # type: ignore[arg-type]
                        fiscal_year=r.fiscal_year,
                        value=r.value,
                        status=r.status,
                    )
                    for r in history
                ],
            )
        )
    as_of = next((r.as_of_date for r in own if r.kind == CURRENT), None)
    return ValuationBandsResponse(
        company_ticker=company.ticker, as_of=as_of, peer_set=set_out, bands=bands
    )
