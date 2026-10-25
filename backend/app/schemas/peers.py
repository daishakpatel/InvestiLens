"""Peer sets and valuation bands (Phase 7h, FR-PS-009..014). Every percentile carries its sample
size `n`, and anything not computed is null with a `reason`, never zero."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

PeerSetKind = Literal["system_default", "user"]


class PeerMember(BaseModel):
    ticker: str
    name: str
    rationale: str  # "same SIC 3674; market cap 1.8x target" (times sign), or "chosen by you"


class PeerSetOut(BaseModel):
    id: int
    name: str
    kind: PeerSetKind
    members: list[PeerMember]
    insufficient: bool  # fewer than three members: peer percentiles are hidden (DR-PS-001)
    reason: str | None = None  # why a default set is short


class PeerSetsResponse(BaseModel):
    company_ticker: str
    peer_sets: list[PeerSetOut]


class PeerSetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    tickers: list[str] = Field(min_length=1, max_length=12)


class PeerSetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    tickers: list[str] | None = Field(default=None, min_length=1, max_length=12)


class HistoryPoint(BaseModel):
    as_of: date
    kind: Literal["fiscal_year_end", "current"]
    fiscal_year: int | None = None
    value: Decimal | None  # only when status is ok
    status: str  # ok | not_meaningful | missing_input | not_applicable


class OwnBand(BaseModel):
    """Today's value within the company's own fiscal-year-end values (and today's)."""

    n: int
    min: Decimal | None = None
    median: Decimal | None = None
    max: Decimal | None = None
    percentile: Decimal | None = None  # fraction at or below today (0.8 = 80th percentile)
    label: str | None = None  # positional only: "in the top quartile of its 5-year range"
    reason: str | None = None


class ExcludedPeer(BaseModel):
    ticker: str
    reason: str


class PeerBand(BaseModel):
    n: int
    median: Decimal | None = None
    percentile: Decimal | None = None
    premium_to_peer_median: Decimal | None = None  # 0.18 = 18% above the peer median
    label: str | None = None  # "18% above peer median"
    reason: str | None = None
    excluded: list[ExcludedPeer] = []


class ValuationBand(BaseModel):
    multiple: str
    unit: Literal["x", "ratio"]  # multiples print as 12.3x, yields as a percentage
    status: str  # today's status; a band is drawn only when ok
    value: Decimal | None = None
    reason: str | None = None  # why there is no value today
    own: OwnBand
    peers: PeerBand
    history: list[HistoryPoint]


class ValuationBandsResponse(BaseModel):
    company_ticker: str
    as_of: date | None  # the latest close the "today" values use
    peer_set: PeerSetOut | None
    bands: list[ValuationBand]
    disclaimer: str = "Positions within ranges, not judgements of value. Not investment advice."
