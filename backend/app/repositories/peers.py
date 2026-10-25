"""Peer-set persistence (Phase 7h, FR-PS-001/003, ADR-0046)."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete, insert, or_, select
from sqlalchemy.orm import Session

from app.models import Company, PeerSet, PeerSetMember, ValuationHistory

SYSTEM_DEFAULT = "system_default"
USER = "user"


def default_set(session: Session, company_id: int) -> PeerSet | None:
    return session.scalar(
        select(PeerSet).where(PeerSet.company_id == company_id, PeerSet.kind == SYSTEM_DEFAULT)
    )


def visible_sets(session: Session, company_id: int, user_id: int | None) -> list[PeerSet]:
    """The company's system default and, for a signed-in user, that user's own sets only."""
    owner = PeerSet.kind == SYSTEM_DEFAULT
    if user_id is not None:
        owner = or_(owner, PeerSet.owner_user_id == user_id)
    return list(
        session.scalars(
            select(PeerSet)
            .where(PeerSet.company_id == company_id, owner)
            .order_by(PeerSet.kind.desc(), PeerSet.id)  # system_default before user
        )
    )


def get_visible(session: Session, set_id: int, user_id: int | None) -> PeerSet | None:
    """A set the caller may see: a system default, or their own (others' sets do not exist)."""
    found = session.get(PeerSet, set_id)
    if found is None or (found.kind == USER and found.owner_user_id != user_id):
        return None
    return found


def members(session: Session, set_ids: Sequence[int]) -> list[tuple[PeerSetMember, Company]]:
    if not set_ids:
        return []
    rows = session.execute(
        select(PeerSetMember, Company)
        .join(Company, Company.id == PeerSetMember.peer_company_id)
        .where(PeerSetMember.peer_set_id.in_(list(set_ids)))
        .order_by(PeerSetMember.peer_set_id, PeerSetMember.position, Company.ticker)
    )
    return [(member, company) for member, company in rows]


def replace_members(session: Session, peer_set_id: int, rows: Sequence[tuple[int, str]]) -> None:
    """Replace a set's members with `(company_id, rationale)` in order."""
    session.execute(delete(PeerSetMember).where(PeerSetMember.peer_set_id == peer_set_id))
    if rows:
        session.execute(
            insert(PeerSetMember),
            [
                {
                    "peer_set_id": peer_set_id,
                    "peer_company_id": cid,
                    "rationale": why,
                    "position": i,
                }
                for i, (cid, why) in enumerate(rows)
            ],
        )


def history(session: Session, company_ids: Sequence[int]) -> list[ValuationHistory]:
    if not company_ids:
        return []
    return list(
        session.scalars(
            select(ValuationHistory)
            .where(ValuationHistory.company_id.in_(list(company_ids)))
            .order_by(ValuationHistory.company_id, ValuationHistory.as_of_date)
        )
    )
