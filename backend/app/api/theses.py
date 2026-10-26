"""Investment thesis tracker endpoints (Phase 7k, FR-TH-013/014, SEC-TH-001, ADR-0049).

Every route needs a signed-in user, and every lookup is scoped to that user: another user's
thesis, KPI, event or revision answers 404, exactly like one that does not exist. Deleting a
thesis hard-deletes its KPIs, events and revisions. Thesis text never appears in logs.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_current_user_id
from app.api.errors import ProblemException
from app.api.rate_limit_backends import MemoryRateLimiter
from app.billing.budget import check_budget
from app.config import get_settings
from app.db import get_db
from app.models import Company, Thesis, ThesisKpi, User
from app.repositories import companies as company_repo
from app.repositories import theses as repo
from app.schemas.common import FieldError
from app.schemas.thesis import (
    DraftRequest,
    DraftResponse,
    Kpi,
    KpiCreate,
    KpiUpdate,
    MetricRegistryResponse,
    NoteCreate,
    ThesisCreate,
    ThesisDetail,
    ThesisEvent,
    ThesisRevision,
    ThesisSummary,
    ThesisUpdate,
)
from app.thesis import draft as draft_service
from app.thesis import service
from app.thesis.service import ThesisError

router = APIRouter(tags=["Theses"])

_DB = Depends(get_db, scope="function")
_USER_ID = Depends(get_current_user_id)
_USER = Depends(get_current_user)
# shortcut: per-process counter (as for earnings briefs); Redis limiter once multi-process.
_drafts = MemoryRateLimiter()
_NOT_FOUND = ProblemException(status.HTTP_404_NOT_FOUND, "Not Found", "Thesis not found.")


def _problem(exc: ThesisError) -> ProblemException:
    errors = [FieldError(field=exc.field, message=exc.detail)] if exc.field else None
    return ProblemException(exc.status, exc.title, exc.detail, errors=errors)


def _owned(db: Session, thesis_id: int, user_id: int) -> Thesis:
    thesis = repo.owned(db, thesis_id, user_id)
    if thesis is None:
        raise _NOT_FOUND
    return thesis


def _owned_kpi(db: Session, thesis: Thesis, kpi_id: int) -> ThesisKpi:
    kpi = repo.kpi(db, thesis.id, kpi_id)
    if kpi is None:
        raise ProblemException(status.HTTP_404_NOT_FOUND, "Not Found", "KPI not found.")
    return kpi


@router.get("/theses", response_model=list[ThesisSummary])
def list_theses(
    ticker: str | None = Query(default=None, max_length=12),
    db: Session = _DB,
    user_id: int = _USER_ID,
) -> list[ThesisSummary]:
    """The caller's theses, most recently updated first; `ticker` narrows to one company."""
    company_id = None
    if ticker:
        company = company_repo.get_by_ticker(db, ticker.upper())
        if company is None:
            return []
        company_id = company.id
    return service.summaries(db, user_id, company_id=company_id)


@router.post("/theses", status_code=201, response_model=ThesisDetail)
def create_thesis(body: ThesisCreate, db: Session = _DB, user_id: int = _USER_ID) -> ThesisDetail:
    try:
        thesis = service.create(db, user_id, body)
    except ThesisError as exc:
        raise _problem(exc) from exc
    db.commit()
    return service.detail(db, thesis)


@router.get("/theses/{thesis_id}", response_model=ThesisDetail)
def get_thesis(thesis_id: int, db: Session = _DB, user_id: int = _USER_ID) -> ThesisDetail:
    return service.detail(db, _owned(db, thesis_id, user_id))


@router.patch("/theses/{thesis_id}", response_model=ThesisDetail)
def update_thesis(
    thesis_id: int, body: ThesisUpdate, db: Session = _DB, user_id: int = _USER_ID
) -> ThesisDetail:
    thesis = _owned(db, thesis_id, user_id)
    try:
        service.update(db, thesis, body)
    except ThesisError as exc:
        raise _problem(exc) from exc
    db.commit()
    return service.detail(db, thesis)


@router.delete("/theses/{thesis_id}", status_code=204)
def delete_thesis(thesis_id: int, db: Session = _DB, user_id: int = _USER_ID) -> Response:
    """Hard delete: the thesis, its KPIs, events and revisions (FR-TH-014)."""
    repo.delete_thesis(db, _owned(db, thesis_id, user_id))
    db.commit()
    return Response(status_code=204)


@router.post("/theses/{thesis_id}/kpis", status_code=201, response_model=Kpi)
def add_kpi(thesis_id: int, body: KpiCreate, db: Session = _DB, user_id: int = _USER_ID) -> Kpi:
    thesis = _owned(db, thesis_id, user_id)
    try:
        kpi = service.add_kpi(db, thesis, body)
    except ThesisError as exc:
        raise _problem(exc) from exc
    db.commit()
    return _kpi_detail(db, thesis, kpi.id)


@router.patch("/theses/{thesis_id}/kpis/{kpi_id}", response_model=Kpi)
def update_kpi(
    thesis_id: int, kpi_id: int, body: KpiUpdate, db: Session = _DB, user_id: int = _USER_ID
) -> Kpi:
    thesis = _owned(db, thesis_id, user_id)
    try:
        service.update_kpi(db, thesis, _owned_kpi(db, thesis, kpi_id), body)
    except ThesisError as exc:
        raise _problem(exc) from exc
    db.commit()
    return _kpi_detail(db, thesis, kpi_id)


@router.delete("/theses/{thesis_id}/kpis/{kpi_id}", status_code=204)
def delete_kpi(thesis_id: int, kpi_id: int, db: Session = _DB, user_id: int = _USER_ID) -> Response:
    thesis = _owned(db, thesis_id, user_id)
    db.delete(_owned_kpi(db, thesis, kpi_id))
    db.commit()
    return Response(status_code=204)


def _kpi_detail(db: Session, thesis: Thesis, kpi_id: int) -> Kpi:
    return next(k for k in service.detail(db, thesis).kpis if k.id == kpi_id)


@router.get("/theses/{thesis_id}/events", response_model=list[ThesisEvent])
def list_events(
    thesis_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = _DB,
    user_id: int = _USER_ID,
) -> list[ThesisEvent]:
    """The timeline, newest first."""
    thesis = _owned(db, thesis_id, user_id)
    return [service.event_out(e) for e in repo.events(db, thesis.id, limit=limit)]


@router.post("/theses/{thesis_id}/events", status_code=201, response_model=ThesisEvent)
def add_note(
    thesis_id: int, body: NoteCreate, db: Session = _DB, user_id: int = _USER_ID
) -> ThesisEvent:
    """A user note on the timeline."""
    event = service.add_note(db, _owned(db, thesis_id, user_id), body.note)
    db.commit()
    return service.event_out(event)


@router.get("/theses/{thesis_id}/revisions", response_model=list[ThesisRevision])
def list_revisions(
    thesis_id: int, db: Session = _DB, user_id: int = _USER_ID
) -> list[ThesisRevision]:
    """Every saved title and body, newest first, each with a word diff against the previous."""
    return service.revisions(db, _owned(db, thesis_id, user_id))


@router.post("/theses/draft", response_model=DraftResponse)
def draft_thesis(body: DraftRequest, db: Session = _DB, user: User = _USER) -> DraftResponse:
    """Suggested title and KPIs from the caller's own notes; nothing is saved (FR-TH-010)."""
    allowed, retry_after = _drafts.allow(
        key=f"thesis_draft:user:{user.id}",
        limit=get_settings().thesis_draft_per_hour,
        window_seconds=3600,
    )
    if not allowed:
        raise ProblemException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too Many Requests",
            f"Draft limit reached; retry in {retry_after}s.",
        )
    check_budget(db, user)
    try:
        company = service.company_for(db, body.ticker)
    except ThesisError as exc:
        raise _problem(exc) from exc
    result = draft_service.draft(db, company, body.notes, user_id=user.id)
    db.commit()  # the llm_calls row (token counts only)
    return result


@router.get("/thesis/metric-registry", response_model=MetricRegistryResponse)
def metric_registry(
    ticker: str | None = Query(default=None, max_length=12), db: Session = _DB
) -> MetricRegistryResponse:
    """Trackable metrics with unit, periods and (for `ticker`) sector applicability."""
    company: Company | None = None
    if ticker:
        company = company_repo.get_by_ticker(db, ticker.upper())
        if company is None:
            raise ProblemException(status.HTTP_404_NOT_FOUND, "Not Found", "Unknown ticker.")
    return service.metric_registry(company)
