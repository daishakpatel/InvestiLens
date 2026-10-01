"""Mock provider tests (Phase 0d DoD, DR-004). Offline — no DB, no network.

Each mock must return schema-valid responses shaped exactly like the real provider will.
"""

from __future__ import annotations

import asyncio

from app.config import get_settings
from app.providers import (
    get_embedding_client,
    get_filings_provider,
    get_llm_client,
    get_news_provider,
    get_price_provider,
)
from app.providers.base import LLMMessage
from app.schemas.company import Company, PricePoint
from app.schemas.filings import FilingDetail, FilingSummary
from app.schemas.news import NewsItem


def test_default_provider_mode_is_mock() -> None:
    assert get_settings().provider_mode == "mock"  # CI default (DR-004)


def test_filings_mock_resolves_and_lists() -> None:
    provider = get_filings_provider()
    company = asyncio.run(provider.resolve_company("NVDA"))
    assert isinstance(company, Company)
    assert company.cik == "0001045810"

    by_cik = asyncio.run(provider.resolve_company("0000320193"))
    assert by_cik is not None and by_cik.ticker == "AAPL"

    filings = asyncio.run(provider.list_filings("0001045810"))
    assert filings and all(isinstance(f, FilingSummary) for f in filings)
    tenk = next(f for f in filings if f.filing_type == "10-K")
    detail = asyncio.run(provider.get_filing(tenk.accession_number))
    assert isinstance(detail, FilingDetail) and detail.company_ticker == "NVDA"


def test_unknown_company_returns_none() -> None:
    assert asyncio.run(get_filings_provider().resolve_company("ZZZZ")) is None


def test_price_mock_returns_two_weeks() -> None:
    points = asyncio.run(get_price_provider().get_prices("NVDA"))
    assert len(points) == 10  # ~2 weeks of trading days
    assert all(isinstance(p, PricePoint) for p in points)
    assert points[0].close is not None


def test_news_mock_returns_items() -> None:
    items = asyncio.run(get_news_provider().get_news("AAPL"))
    assert 10 <= len(items) <= 20
    assert all(isinstance(n, NewsItem) for n in items)


def test_embedding_mock_is_deterministic_and_right_dim() -> None:
    client = get_embedding_client()
    dim = client.dimension
    assert dim == 1024  # ADR-0010
    first = asyncio.run(client.embed(["revenue grew"]))
    second = asyncio.run(client.embed(["revenue grew"]))
    assert len(first[0]) == dim
    assert first == second  # deterministic
    norm = sum(x * x for x in first[0]) ** 0.5
    assert abs(norm - 1.0) < 1e-6  # unit vector


def test_llm_mock_replays_recording() -> None:
    client = get_llm_client()
    messages = [
        LLMMessage("system", "You are a financial research assistant. Use only provided evidence."),
        LLMMessage("user", "What was NVIDIA's FY2025 revenue? [SOURCE:xbrl_nvda_revenue_FY2025]"),
    ]
    answer = asyncio.run(client.complete(messages, model="claude-haiku-4-5", max_tokens=256))
    assert "130.5B" in answer  # replayed from the recorded fixture


def test_llm_mock_stub_is_deterministic_on_miss() -> None:
    client = get_llm_client()
    messages = [LLMMessage("user", "an unrecorded prompt")]
    a = asyncio.run(client.complete(messages, model="claude-haiku-4-5", max_tokens=16))
    b = asyncio.run(client.complete(messages, model="claude-haiku-4-5", max_tokens=16))
    assert a == b and a.startswith("MOCK_COMPLETION[")
