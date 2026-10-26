"""Thesis persistence (Phase 7k). Every user-facing read takes the user's id: a thesis that is not
the caller's is indistinguishable from one that does not exist (SEC-TH-001)."""

from __future__ import annotations

from collections.abc import Collection, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import (
    Company,
    EarningsBrief,
    Filing,
    RedFlag,
    Thesis,
    ThesisEvent,
    ThesisKpi,
    ThesisRevision,
)


def owned(session: Session, thesis_id: int, user_id: int) -> Thesis | None:
    return session.scalar(select(Thesis).where(Thesis.id == thesis_id, Thesis.user_id == user_id))


def list_for_user(
    session: Session, user_id: int, *, company_id: int | None = None
) -> list[tuple[Thesis, str]]:
    """The user's theses with their ticker, most recently updated first."""
    query = (
        select(Thesis, Company.ticker)
        .join(Company, Company.id == Thesis.company_id)
        .where(Thesis.user_id == user_id)
        .order_by(Thesis.updated_at.desc(), Thesis.id.desc())
    )
    if company_id is not None:
        query = query.where(Thesis.company_id == company_id)
    return [(thesis, ticker) for thesis, ticker in session.execute(query)]


def count_active(session: Session, user_id: int) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(Thesis)
            .where(Thesis.user_id == user_id, Thesis.status == "active")
        )
        or 0
    )


def active_for_company(session: Session, company_id: int) -> list[Thesis]:
    """Every user's active theses on a company (system jobs only; never returned to a user)."""
    return list(
        session.scalars(
            select(Thesis).where(Thesis.company_id == company_id, Thesis.status == "active")
        )
    )


def kpis(session: Session, thesis_ids: Collection[int]) -> list[ThesisKpi]:
    if not thesis_ids:
        return []
    return list(
        session.scalars(
            select(ThesisKpi)
            .where(ThesisKpi.thesis_id.in_(thesis_ids))
            .order_by(ThesisKpi.thesis_id, ThesisKpi.id)
        )
    )


def kpi(session: Session, thesis_id: int, kpi_id: int) -> ThesisKpi | None:
    return session.scalar(
        select(ThesisKpi).where(ThesisKpi.id == kpi_id, ThesisKpi.thesis_id == thesis_id)
    )


def events(session: Session, thesis_id: int, *, limit: int) -> list[ThesisEvent]:
    return list(
        session.scalars(
            select(ThesisEvent)
            .where(ThesisEvent.thesis_id == thesis_id)
            .order_by(ThesisEvent.occurred_at.desc(), ThesisEvent.id.desc())
            .limit(limit)
        )
    )


def revisions(session: Session, thesis_id: int) -> list[ThesisRevision]:
    return list(
        session.scalars(
            select(ThesisRevision)
            .where(ThesisRevision.thesis_id == thesis_id)
            .order_by(ThesisRevision.revision)
        )
    )


def add_revision(session: Session, thesis: Thesis) -> ThesisRevision:
    latest = session.scalar(
        select(func.max(ThesisRevision.revision)).where(ThesisRevision.thesis_id == thesis.id)
    )
    row = ThesisRevision(
        thesis_id=thesis.id, revision=(latest or 0) + 1, title=thesis.title, body_md=thesis.body_md
    )
    session.add(row)
    return row


def delete_thesis(session: Session, thesis: Thesis) -> None:
    """Hard delete; KPIs, events and revisions go with it (FK cascade, FR-TH-014)."""
    session.execute(delete(Thesis).where(Thesis.id == thesis.id))


def link_events(session: Session, rows: Sequence[dict[str, Any]]) -> int:
    """Red-flag / brief links, each at most once per thesis (`uq_thesis_events_link`)."""
    if not rows:
        return 0
    result = session.execute(
        insert(ThesisEvent)
        .values(list(rows))
        .on_conflict_do_nothing(
            index_elements=["thesis_id", "kind", "ref_id"],
            index_where=ThesisEvent.kind.in_(("red_flag", "brief_published")),
        )
        .returning(ThesisEvent.id)
    )
    return len(result.all())


def flags_since(
    session: Session, company_id: int, taxonomy_version: str, after: datetime
) -> list[tuple[RedFlag, Filing]]:
    return [
        (flag, filing)
        for flag, filing in session.execute(
            select(RedFlag, Filing)
            .join(Filing, Filing.id == RedFlag.filing_id)
            .where(
                RedFlag.company_id == company_id,
                RedFlag.taxonomy_version == taxonomy_version,
                RedFlag.detected_at > after,
            )
        )
    ]


def first_briefs_since(session: Session, company_id: int, after: datetime) -> list[EarningsBrief]:
    """Each quarter's first preview / brief version stored after `after`."""
    return list(
        session.scalars(
            select(EarningsBrief).where(
                EarningsBrief.company_id == company_id,
                EarningsBrief.version == 1,
                EarningsBrief.created_at > after,
            )
        )
    )


def kpi_events_between(
    session: Session,
    user_id: int,
    *,
    kinds: Collection[str],
    company_id: int | None,
    after: datetime,
    until: datetime,
) -> list[tuple[ThesisEvent, ThesisKpi, Thesis, str]]:
    """The user's KPI transitions in (after, until], with KPI, thesis and ticker (alerts)."""
    query = (
        select(ThesisEvent, ThesisKpi, Thesis, Company.ticker)
        .join(ThesisKpi, ThesisKpi.id == ThesisEvent.kpi_id)
        .join(Thesis, Thesis.id == ThesisEvent.thesis_id)
        .join(Company, Company.id == Thesis.company_id)
        .where(
            Thesis.user_id == user_id,
            ThesisEvent.kind.in_(kinds),
            ThesisEvent.occurred_at > after,
            ThesisEvent.occurred_at <= until,
        )
        .order_by(ThesisEvent.occurred_at, ThesisEvent.id)
    )
    if company_id is not None:
        query = query.where(Thesis.company_id == company_id)
    return [(e, k, t, ticker) for e, k, t, ticker in session.execute(query)]
