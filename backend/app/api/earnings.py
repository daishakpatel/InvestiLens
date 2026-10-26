"""Earnings calendar and briefs (Phase 7j, FR-EB-013, ADR-0048).

`GET .../earnings/calendar` refreshes the company's calendar from stored filings (an idempotent
upsert) and returns it. `GET .../earnings/briefs` lists stored versions. `POST .../earnings/briefs`
is a user-triggered regeneration: signed in, within the AI budget, rate-limited per user, and
answered with the stored version when the inputs have not changed.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.companies import _resolve
from app.api.deps import get_current_user
from app.api.errors import ProblemException
from app.api.rate_limit_backends import MemoryRateLimiter
from app.billing.budget import check_budget
from app.config import get_settings
from app.db import get_db
from app.earnings import service
from app.earnings.calendar import build_calendar, label, upcoming_event
from app.models import EarningsEvent, User
from app.repositories import earnings as repo
from app.schemas.earnings import (
    CalendarEvent,
    EarningsBriefsResponse,
    EarningsCalendarResponse,
    GenerateBriefRequest,
    GenerateBriefResponse,
    Kind,
)

router = APIRouter(tags=["Earnings"])

_DB = Depends(get_db, scope="function")
_USER = Depends(get_current_user)
# shortcut: per-process counter, so N API workers allow N times the limit; move to the Redis
# limiter (rate_limit_backends.RedisRateLimiter) when the API runs more than one process.
_regenerations = MemoryRateLimiter()
_STATUS = {
    "not_covered": status.HTTP_409_CONFLICT,
    "no_period": status.HTTP_409_CONFLICT,
    "daily_cap": status.HTTP_429_TOO_MANY_REQUESTS,
}
METHOD = (
    "Reported dates are Item 2.02 8-K filing dates; an announced date is quoted from the "
    "company's own 8-K or release; an estimate (~) is last year's date for the quarter plus 52 "
    "weeks."
)


def to_event(event: EarningsEvent) -> CalendarEvent:
    return CalendarEvent(
        fiscal_year=event.fiscal_year,
        fiscal_period=event.fiscal_period,
        period_label=label((event.fiscal_year, event.fiscal_period)),
        report_date=event.report_date,
        report_time=event.report_time,  # type: ignore[arg-type]  # CHECK report_time_known
        source=event.source,  # type: ignore[arg-type]
        status=event.status,  # type: ignore[arg-type]
        estimated=event.source == "estimated",
        source_id=event.source_id,
        quote=event.quote,
    )


@router.get("/companies/{ticker}/earnings/calendar", response_model=EarningsCalendarResponse)
def earnings_calendar(ticker: str, db: Session = _DB) -> EarningsCalendarResponse:
    """Reported and upcoming earnings dates, newest quarter first (FR-EB-001/002)."""
    company = _resolve(db, ticker)
    events = build_calendar(db, company)
    db.commit()
    upcoming = upcoming_event(events)
    return EarningsCalendarResponse(
        ticker=company.ticker,
        upcoming=to_event(upcoming) if upcoming else None,
        events=[to_event(e) for e in events],
        method=METHOD,
    )


@router.get("/companies/{ticker}/earnings/briefs", response_model=EarningsBriefsResponse)
def earnings_briefs(
    ticker: str,
    kind: Kind | None = None,
    fiscal_year: int | None = Query(default=None, ge=1990, le=2100),
    fiscal_period: str | None = Query(default=None, pattern="^Q[1-4]$"),
    db: Session = _DB,
) -> EarningsBriefsResponse:
    """Stored preview/brief versions, latest quarter first, then newest version (FR-EB-015)."""
    company = _resolve(db, ticker)
    rows = repo.briefs(
        db, company.id, kind=kind, fiscal_year=fiscal_year, fiscal_period=fiscal_period
    )
    return EarningsBriefsResponse(
        ticker=company.ticker, items=[service.to_stored(r) for r in rows], scope=service.SCOPE
    )


@router.post("/companies/{ticker}/earnings/briefs", response_model=GenerateBriefResponse)
def regenerate_earnings_brief(
    ticker: str, body: GenerateBriefRequest, db: Session = _DB, user: User = _USER
) -> GenerateBriefResponse:
    """Make (or return the unchanged) preview or brief for the company's current quarter."""
    company = _resolve(db, ticker)
    allowed, retry_after = _regenerations.allow(
        key=f"earnings_brief:user:{user.id}",
        limit=get_settings().earnings_brief_regen_per_hour,
        window_seconds=3600,
    )
    if not allowed:
        raise ProblemException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too Many Requests",
            f"Brief regeneration limit reached; retry in {retry_after}s.",
        )
    check_budget(db, user)
    try:
        row, created = service.generate(db, company, body.kind, user_id=user.id)
    except service.BriefUnavailable as exc:
        raise ProblemException(_STATUS[exc.code], "Brief not available", exc.message) from exc
    db.commit()
    return GenerateBriefResponse(created=created, item=service.to_stored(row))
