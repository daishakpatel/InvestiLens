"""Peer sets and valuation bands (Phase 7h, FR-PS-003/012, ADR-0046).

Reads are public; a signed-in caller also sees their own peer sets. A user's set is private: any
other caller gets 404, as if it did not exist (FR-PS-003). Writes need a signed-in user.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.companies import _resolve
from app.api.deps import get_current_user_id, get_optional_user_id
from app.comparison.bands import peer_set_out, valuation_bands
from app.comparison.peers import PeerSetError, save_user_set
from app.db import get_db
from app.models import Company, PeerSet
from app.repositories import peers as peer_repo
from app.schemas.peers import (
    PeerSetCreate,
    PeerSetOut,
    PeerSetsResponse,
    PeerSetUpdate,
    ValuationBandsResponse,
)

router = APIRouter(tags=["Peer sets"])

_DB = Depends(get_db, scope="function")
_USER = Depends(get_current_user_id)
_MAYBE_USER = Depends(get_optional_user_id)
_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "peer set not found")


def visible_set(db: Session, company: Company, set_id: int, user_id: int | None) -> PeerSet:
    """A peer set of this company the caller may see, else 404 (never 403, FR-PS-003)."""
    found = peer_repo.get_visible(db, set_id, user_id)
    if found is None or found.company_id != company.id:
        raise _NOT_FOUND
    return found


def _owned(db: Session, company: Company, set_id: int, user_id: int) -> PeerSet:
    found = visible_set(db, company, set_id, user_id)
    if found.kind != peer_repo.USER:  # the system default is not editable
        raise _NOT_FOUND
    return found


@router.get("/companies/{ticker}/peer-sets", response_model=PeerSetsResponse)
def list_peer_sets(
    ticker: str, db: Session = _DB, user_id: int | None = _MAYBE_USER
) -> PeerSetsResponse:
    company = _resolve(db, ticker)
    sets = peer_repo.visible_sets(db, company.id, user_id)
    return PeerSetsResponse(company_ticker=company.ticker, peer_sets=peer_set_out(db, sets))


@router.post(
    "/companies/{ticker}/peer-sets", response_model=PeerSetOut, status_code=status.HTTP_201_CREATED
)
def create_peer_set(
    ticker: str, body: PeerSetCreate, db: Session = _DB, user_id: int = _USER
) -> PeerSetOut:
    company = _resolve(db, ticker)
    try:
        peer_set = save_user_set(db, company, user_id, name=body.name, tickers=body.tickers)
    except PeerSetError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    db.commit()
    return peer_set_out(db, [peer_set])[0]


@router.patch("/companies/{ticker}/peer-sets/{peer_set_id}", response_model=PeerSetOut)
def update_peer_set(
    ticker: str, peer_set_id: int, body: PeerSetUpdate, db: Session = _DB, user_id: int = _USER
) -> PeerSetOut:
    company = _resolve(db, ticker)
    peer_set = _owned(db, company, peer_set_id, user_id)
    tickers = body.tickers or [c.ticker for _, c in peer_repo.members(db, [peer_set.id])]
    try:
        save_user_set(
            db,
            company,
            user_id,
            name=body.name or peer_set.name,
            tickers=tickers,
            existing=peer_set,
        )
    except PeerSetError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    db.commit()
    return peer_set_out(db, [peer_set])[0]


@router.delete(
    "/companies/{ticker}/peer-sets/{peer_set_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_peer_set(
    ticker: str, peer_set_id: int, db: Session = _DB, user_id: int = _USER
) -> Response:
    company = _resolve(db, ticker)
    db.delete(_owned(db, company, peer_set_id, user_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/companies/{ticker}/valuation-bands", response_model=ValuationBandsResponse)
def get_valuation_bands(
    ticker: str,
    peer_set_id: int | None = Query(default=None, description="Default: the system default set"),
    db: Session = _DB,
    user_id: int | None = _MAYBE_USER,
) -> ValuationBandsResponse:
    company = _resolve(db, ticker)
    peer_set = visible_set(db, company, peer_set_id, user_id) if peer_set_id is not None else None
    return valuation_bands(db, company, peer_set)
