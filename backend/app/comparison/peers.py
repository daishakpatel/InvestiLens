"""Peer-set suggestion by SIC/industry + market-cap band (§37.1), and peer sets v2 (Phase 7h).

`suggest_peers` ranks broad suggestions for the Compare view. `default_peers` is the strict,
stored rule behind each company's system default peer set (FR-PS-002), and the user-set helpers
validate a user's own sets (FR-PS-003).

Deterministic and read-only. Candidates are ranked first by SIC proximity (exact code, then
3-digit industry group, then 2-digit major group, then shared sector), then — when market caps are
available — by market-cap proximity within a band. Market cap is price-dependent and often not yet
persisted (Phase 1d gap); when it is missing the band is skipped and a note is surfaced (never a
silent degradation, per the "surface every degradation" rule).
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.api._support import metric_to_result
from app.config import get_settings
from app.models import Company, PeerSet
from app.repositories import companies as company_repo
from app.repositories import metrics as metric_repo
from app.repositories import peers as peer_repo
from app.schemas.comparison import PeerSuggestion, PeerSuggestionsResponse

# Market caps within this multiplicative band are considered comparable (0.1x-10x the target).
_MARKET_CAP_BAND = (Decimal("0.1"), Decimal("10"))


def _sic_closeness(target: Company, candidate: Company) -> int:
    """0-4 score of SIC proximity; higher is closer. Falls back to shared sector when SIC absent."""
    t, c = target.sic_code, candidate.sic_code
    if t and c:
        if t == c:
            return 4
        if t[:3] == c[:3]:
            return 3
        if t[:2] == c[:2]:
            return 2
    if target.sector and candidate.sector and target.sector == candidate.sector:
        return 1
    return 0


def _market_cap(session: Session, company: Company) -> Decimal | None:
    rows = metric_repo.get_latest_metrics(
        session, company_id=company.id, metric_names=["market_cap"]
    )
    return rows[0].metric_value if rows and rows[0].metric_value is not None else None


def _reason(closeness: int, target: Company, candidate: Company, in_band: bool | None) -> str:
    if closeness == 4:
        base = f"same SIC {candidate.sic_code}"
    elif closeness == 3:
        base = f"same industry group (SIC {candidate.sic_code[:3] if candidate.sic_code else '?'}x)"
    elif closeness == 2:
        base = f"same SIC major group ({candidate.sic_code[:2] if candidate.sic_code else '?'}xx)"
    elif closeness == 1:
        base = f"same sector ({candidate.sector})"
    else:
        base = "broad market"
    if in_band is True:
        base += "; market cap within band"
    elif in_band is False:
        base += "; market cap outside band"
    return base


def suggest_peers(session: Session, ticker: str, *, limit: int = 5) -> PeerSuggestionsResponse:
    """Suggest up to `limit` comparable companies for `ticker` (§37.1)."""
    target = company_repo.get_by_ticker(session, ticker)
    if target is None:
        raise ValueError(f"unknown ticker: {ticker}")

    notes: list[str] = []
    if not target.sic_code and not target.sector:
        notes.append(
            f"{target.ticker} has no SIC/sector classification; peers fall back to broad market."
        )

    target_cap = _market_cap(session, target)
    if target_cap is None:
        notes.append("Market-cap band unavailable (price-dependent metrics not persisted).")

    scored: list[tuple[int, Decimal, PeerSuggestion]] = []
    for candidate in company_repo.list_active(session):
        if candidate.id == target.id:
            continue
        closeness = _sic_closeness(target, candidate)
        cand_cap = _market_cap(session, candidate)

        in_band: bool | None = None
        # Proximity is the absolute log-distance of the cap ratio; unknown caps sort last (large).
        proximity = Decimal(10**9)
        if target_cap is not None and cand_cap is not None and target_cap > 0:
            ratio = cand_cap / target_cap
            in_band = _MARKET_CAP_BAND[0] <= ratio <= _MARKET_CAP_BAND[1]
            proximity = abs(ratio - Decimal(1))

        cap_result = None
        if cand_cap is not None:
            rows = metric_repo.get_latest_metrics(
                session, company_id=candidate.id, metric_names=["market_cap"]
            )
            cap_result = metric_to_result(rows[0]) if rows else None

        suggestion = PeerSuggestion(
            ticker=candidate.ticker,
            name=candidate.name,
            sic_code=candidate.sic_code,
            sector=candidate.sector,
            industry=candidate.industry,
            market_cap=cap_result,
            reason=_reason(closeness, target, candidate, in_band),
        )
        scored.append((closeness, proximity, suggestion))

    # Highest SIC closeness first, then nearest market cap. Drop pure "broad market" (closeness 0)
    # unless nothing else qualifies, so suggestions stay meaningful.
    scored.sort(key=lambda s: (-s[0], s[1]))
    related = [s for s in scored if s[0] > 0]
    chosen = (related or scored)[:limit]
    return PeerSuggestionsResponse(target=target.ticker, peers=[s[2] for s in chosen], notes=notes)


# --- Peer sets v2 (Phase 7h, FR-PS-001..003, ADR-0046) ---------------------------------------
MIN_PEERS = 3  # fewer members: "insufficient peers", percentiles hidden (DR-PS-001)
MAX_USER_PEERS = 12
DEFAULT_NAME = "Default peers"
_TIMES = "\u00d7"  # the multiplication sign, as the UI prints multiples


class PeerSetError(ValueError):
    """A user peer set that cannot be saved as asked; the message says why and what to do."""


def _cap_and_currency(session: Session, company: Company) -> tuple[Decimal | None, str | None]:
    rows = metric_repo.get_latest_metrics(
        session, company_id=company.id, metric_names=["market_cap"]
    )
    row = rows[0] if rows else None
    if row is None or row.metric_value is None:
        return None, None
    return row.metric_value, row.unit


def default_peers(session: Session, target: Company) -> list[tuple[Company, str]]:
    """The deterministic default peers of `target` with a rationale each (FR-PS-002).

    Same SIC code, same reporting currency, market cap within the configured band of the
    target's (default 0.25x-4x), the target excluded, nearest market cap first (ties by ticker),
    at most `peer_set_max_default`. No model is involved; the same data gives the same set.
    """
    settings = get_settings()
    target_cap, currency = _cap_and_currency(session, target)
    if not target.sic_code or target_cap is None or target_cap <= 0:
        return []
    low, high = (
        Decimal(str(settings.peer_market_cap_band_low)),
        Decimal(str(settings.peer_market_cap_band_high)),
    )
    ranked: list[tuple[Decimal, str, Company, Decimal]] = []
    for candidate in company_repo.list_active(session):
        if candidate.id == target.id or candidate.sic_code != target.sic_code:
            continue
        cap, cand_currency = _cap_and_currency(session, candidate)
        if cap is None or cand_currency != currency:
            continue
        ratio = cap / target_cap
        if low <= ratio <= high:
            # Distance on a log scale: 2x and 0.5x are equally far from the target.
            distance = abs(ratio.ln())
            ranked.append((distance, candidate.ticker, candidate, ratio))
    ranked.sort(key=lambda r: (r[0], r[1]))
    return [
        (company, f"same SIC {target.sic_code}; market cap {ratio:.1f}{_TIMES} target")
        for _, _, company, ratio in ranked[: settings.peer_set_max_default]
    ]


def refresh_default_peer_set(session: Session, company: Company) -> PeerSet:
    """Create or rebuild the company's system default set (after its prices and valuation)."""
    found = peer_repo.default_set(session, company.id)
    if found is None:
        found = PeerSet(
            company_id=company.id,
            owner_user_id=None,
            name=DEFAULT_NAME,
            kind=peer_repo.SYSTEM_DEFAULT,
        )
        session.add(found)
        session.flush()
    peer_repo.replace_members(
        session, found.id, [(c.id, why) for c, why in default_peers(session, company)]
    )
    return found


def resolve_user_tickers(session: Session, company: Company, tickers: list[str]) -> list[Company]:
    """Validate a user set's tickers (FR-PS-003): 1-12 distinct, known, not the company itself.
    Unknown tickers are named, never silently dropped."""
    wanted = list(dict.fromkeys(t.strip().upper() for t in tickers if t.strip()))
    if not wanted:
        raise PeerSetError("A peer set needs at least one ticker.")
    if len(wanted) > MAX_USER_PEERS:
        raise PeerSetError(f"A peer set holds at most {MAX_USER_PEERS} companies.")
    if company.ticker in wanted:
        raise PeerSetError(f"{company.ticker} cannot be its own peer.")
    found = company_repo.get_many_by_ticker(session, wanted)
    unknown = [t for t in wanted if t not in found]
    if unknown:
        raise PeerSetError(
            f"Not in Assay Desk yet: {', '.join(unknown)}. Add this company to your watchlist "
            "first so its filings are ingested, then add it to a peer set."
        )
    return [found[t] for t in wanted]


def save_user_set(
    session: Session,
    company: Company,
    user_id: int,
    *,
    name: str,
    tickers: list[str],
    existing: PeerSet | None = None,
) -> PeerSet:
    """Create a user's set, or replace an existing one's name and members."""
    peers = resolve_user_tickers(session, company, tickers)
    peer_set = existing or PeerSet(
        company_id=company.id, owner_user_id=user_id, name=name, kind=peer_repo.USER
    )
    peer_set.name = name
    if existing is None:
        session.add(peer_set)
    session.flush()
    peer_repo.replace_members(session, peer_set.id, [(p.id, "chosen by you") for p in peers])
    return peer_set
