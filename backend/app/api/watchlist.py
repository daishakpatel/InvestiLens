"""Watchlist, alerts, and feedback endpoints (spec §24.2). [P2 behaviour]"""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.chat import FeedbackRequest
from app.schemas.watchlist import Alert, AlertCreate, Watchlist, WatchlistCreate

router = APIRouter(tags=["Watchlist & Alerts"])


@router.get("/watchlists", response_model=list[Watchlist])
async def list_watchlists() -> list[Watchlist]:
    return []


@router.post("/watchlists", status_code=201, response_model=Watchlist)
async def create_watchlist(body: WatchlistCreate) -> Watchlist:
    return Watchlist(id="wl_example", name=body.name, items=[])


@router.delete("/watchlists/{watchlist_id}", status_code=204)
async def delete_watchlist(watchlist_id: str) -> None:
    return None


@router.get("/alerts", response_model=list[Alert])
async def list_alerts() -> list[Alert]:
    return []


@router.post("/alerts", status_code=201, response_model=Alert)
async def create_alert(body: AlertCreate) -> Alert:
    return Alert(
        id="al_example",
        ticker=body.ticker,
        alert_type=body.alert_type,
        channel=body.channel,
        is_active=True,
    )


@router.delete("/alerts/{alert_id}", status_code=204)
async def delete_alert(alert_id: str) -> None:
    return None


@router.post("/feedback/report", status_code=204, tags=["Feedback"])
async def report_feedback(body: FeedbackRequest) -> None:
    return None
