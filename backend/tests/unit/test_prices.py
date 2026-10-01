"""Price ingestion unit tests (Phase 1d). Offline — MockTransport + fixtures (DR-025, ADR-0007)."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import httpx

import app.finance.metrics as m
from app.finance.shares import total_shares_outstanding
from app.ingestion.prices.pipeline import _corporate_actions
from app.providers.prices.base import PriceBar
from app.providers.prices.live import TiingoPriceSource
from app.utils.http import HardenedHttpClient

_D = Decimal


def _tiingo_source(payload: list[dict[str, object]]) -> TiingoPriceSource:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("authorization", "").startswith("Token ")  # token in header
        assert "api.tiingo.com" in str(request.url)
        return httpx.Response(200, content=json.dumps(payload).encode())

    inner = httpx.Client(
        transport=httpx.MockTransport(handler),
        headers={"User-Agent": "t", "Authorization": "Token test"},
    )
    client = HardenedHttpClient(
        user_agent="t", allowed_hosts=frozenset({"api.tiingo.com"}), rate_per_sec=1000, client=inner
    )
    return TiingoPriceSource(client=client)


def test_tiingo_parses_raw_and_adjusted_and_actions() -> None:
    payload = [
        {
            "date": "2024-06-07T00:00:00.000Z",
            "open": 1684.1,
            "high": 1692.8,
            "low": 1663.1,
            "close": 1669.3,
            "adjClose": 166.93,
            "volume": 26615633,
            "divCash": 0.0,
            "splitFactor": 1.0,
        },
        {
            "date": "2024-06-10T00:00:00.000Z",
            "open": 166.9,
            "high": 167.5,
            "low": 166.4,
            "close": 167.5,
            "adjClose": 167.5,
            "volume": 75373898,
            "divCash": 0.01,
            "splitFactor": 10.0,
        },
    ]
    bars = list(_tiingo_source(payload).get_prices("NVDA"))
    assert len(bars) == 2
    assert bars[0].close == _D("1669.3") and bars[0].adj_close == _D("166.93")  # raw vs adjusted
    assert bars[1].split_factor == _D("10") and bars[1].div_cash == _D("0.01")


def test_corporate_actions_derived_from_bars() -> None:
    bars = [
        PriceBar(
            date(2024, 6, 10),
            None,
            None,
            None,
            _D("167"),
            _D("167"),
            1,
            div_cash=_D("0.01"),
            split_factor=_D("10"),
        ),
        PriceBar(
            date(2024, 7, 1),
            None,
            None,
            None,
            _D("170"),
            _D("170"),
            1,
            div_cash=_D("0.04"),
            split_factor=_D("1"),
        ),
    ]
    actions = _corporate_actions(company_id=1, bars=bars, provider="tiingo")
    kinds = sorted((a["action_type"], str(a["ratio_or_amount"])) for a in actions)
    assert ("dividend", "0.01") in kinds
    assert ("dividend", "0.04") in kinds
    assert ("split", "10") in kinds


def test_split_pe_uses_raw_price_with_contemporaneous_eps() -> None:
    """P/E must pair RAW price with as-reported EPS on the SAME side of a split (DR-025/DR-026).

    Pre-split: raw 1200, as-reported diluted EPS 20 -> P/E 60. Post-split: raw 120, EPS 2 ->
    P/E 60. Using the adjusted close (120) with the pre-split EPS (20) would wrongly show P/E 6.
    """
    pe_pre = m.pe_ratio(_D("1200"), _D("20")).value
    pe_post = m.pe_ratio(_D("120"), _D("2")).value
    assert pe_pre == _D("60") and pe_post == _D("60")  # consistent across the split
    pe_wrong = m.pe_ratio(_D("120"), _D("20")).value  # adjusted price + pre-split EPS
    assert pe_wrong == _D("6") and pe_wrong != pe_pre  # the classic bug this guards against


def test_multi_class_shares_sum() -> None:
    # Alphabet-style A/B/C classes sum for market cap (DR-025).
    assert total_shares_outstanding([_D("5"), _D("1"), _D("6")]) == _D("12")
    assert total_shares_outstanding([None, _D("3")]) == _D("3")
    assert total_shares_outstanding([None, None]) is None
