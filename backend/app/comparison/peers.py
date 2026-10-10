"""Peer-set suggestion by SIC/industry + market-cap band (§37.1).

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
from app.models import Company
from app.repositories import companies as company_repo
from app.repositories import metrics as metric_repo
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
