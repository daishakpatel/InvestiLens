"""Watchlist and alert schemas (spec §24.2, §26.2). [P2 behaviour]"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class WatchlistItem(BaseModel):
    ticker: str


class Watchlist(BaseModel):
    id: str
    name: str
    items: list[WatchlistItem] = []


class WatchlistCreate(BaseModel):
    name: str


class Alert(BaseModel):
    id: str
    ticker: str
    alert_type: Literal["new_10k", "new_10q", "new_8k", "price_move", "news_category"]
    channel: Literal["email", "in_app"] = "in_app"
    is_active: bool = True


class AlertCreate(BaseModel):
    ticker: str
    alert_type: Literal["new_10k", "new_10q", "new_8k", "price_move", "news_category"]
    channel: Literal["email", "in_app"] = "in_app"
