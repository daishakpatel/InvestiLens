"""News ingestion unit tests (Phase 1e). Offline (spec §10.8, §15, LGL-004, ADR-0008)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from app.ingestion.news.classify import CATEGORIES, categorize, publisher_tier
from app.ingestion.news.dedup import ClusterInput, cluster_articles, content_hash
from app.ingestion.news.relevance import relevance_score
from app.ingestion.news.summarize import two_sentence_summary
from app.providers.news.live import FinnhubNewsSource
from app.utils.http import HardenedHttpClient

_D = Decimal


def test_categorize_into_fixed_taxonomy() -> None:
    assert categorize("NVIDIA reports record quarterly revenue") == "Earnings"
    assert categorize("Company to acquire rival in $2B deal") == "M&A"
    assert categorize("Regulators open antitrust probe") == "Regulation"
    assert categorize("New CEO appointed") == "Management"
    assert categorize("Unveils next-gen chip") == "Product"
    assert categorize("Something totally unrelated") == "Industry"  # default
    assert categorize("x") in CATEGORIES


def test_publisher_tier() -> None:
    assert publisher_tier("Reuters") == 4  # §15 reputable financial news
    assert publisher_tier("Bloomberg") == 4
    assert publisher_tier("Some Random Blog") == 5


def test_relevance_scoring_and_passing_mention() -> None:
    threshold = _D("0.3")
    title_hit = relevance_score("NVIDIA Corporation", "NVDA", "NVIDIA beats estimates", "")
    summary_hit = relevance_score(
        "NVIDIA Corporation", "NVDA", "Chip sector update", "NVIDIA among names mentioned"
    )
    passing = relevance_score(
        "NVIDIA Corporation", "NVDA", "Tech stocks rally broadly", "Markets rose on rate optimism"
    )
    assert title_hit > threshold and summary_hit > threshold
    assert passing < threshold  # DoD: passing mention below the display threshold


def test_relevance_matches_whole_words_only() -> None:  # §10.8 entity resolution
    def title_hit(name: str, ticker: str, title: str) -> bool:
        return relevance_score(name, ticker, title) == _D("0.9")

    assert title_hit("INTEL CORP", "INTC", "Intel's foundry wins a customer")
    assert not title_hit("INTEL CORP", "INTC", "US still sharing intelligence with Ukraine")
    # "Advanced" alone is too common; the first two words of the name are used instead.
    assert title_hit("ADVANCED MICRO DEVICES INC", "AMD", "Advanced Micro Devices beats")
    assert not title_hit("ADVANCED MICRO DEVICES INC", "AMD", "Advanced packaging demand grows")
    assert title_hit("ADVANCED MICRO DEVICES INC", "AMD", "Shares of NASDAQ:AMD jump")
    assert not title_hit("ADVANCED MICRO DEVICES INC", "AMD", "Amdocs raises guidance")
    assert title_hit("JPMORGAN CHASE & CO", "JPM", "JPMorgan raises its dividend")
    assert title_hit("JPMORGAN CHASE & CO", "JPM", "One year in, JPMorganChase's security push")
    # Tickers count only in capitals, and a one-letter ticker only as "(A)" or "NYSE:A".
    assert not title_hit("ON Semiconductor Corp", "ON", "Stocks on the move")
    assert title_hit("ON Semiconductor Corp", "ON", "Why ON stock fell today")
    assert not title_hit("Agilent Technologies", "A", "A stock to buy now")
    assert title_hit("Agilent Technologies", "A", "Agilent (A) tops estimates")


def test_content_hash_normalizes() -> None:
    assert content_hash("NVIDIA Unveils Chip!") == content_hash("nvidia  unveils chip")


def test_cluster_exact_and_near_duplicates() -> None:
    now = datetime(2026, 9, 25, 12, tzinfo=UTC)
    items = [
        ClusterInput(content_hash("Nvidia unveils Blackwell"), now),
        ClusterInput(content_hash("Nvidia unveils Blackwell"), now),  # exact dup
        ClusterInput(content_hash("Nvidia reveals Blackwell GPU"), now),  # near dup
        ClusterInput(content_hash("Apple reports earnings"), now),  # distinct
    ]
    # Controlled embeddings: first three are near-identical, the last is orthogonal.
    embeddings = [[1.0, 0.0], [1.0, 0.0], [0.99, 0.01], [0.0, 1.0]]
    clusters = cluster_articles(items, embeddings, cosine_threshold=0.9, window_days=3)
    assert clusters[0] == clusters[1] == clusters[2]  # the one story collapses
    assert clusters[3] != clusters[0]  # the distinct story stays separate


def test_two_sentence_summary_is_traceable() -> None:
    source = "NVIDIA beat revenue estimates. Margins expanded. Guidance was raised again."
    summary = two_sentence_summary("NVIDIA earnings", source)
    assert summary == "NVIDIA beat revenue estimates. Margins expanded."
    for sentence in summary.split(". "):
        assert sentence.strip(".") in source  # every sentence traces to the source (FR-025)


def test_finnhub_parses_headline_level_only() -> None:
    payload = [
        {
            "id": 1,
            "headline": "NVIDIA unveils chip",
            "summary": "A short summary.",
            "url": "https://ex/1",
            "source": "Reuters",
            "datetime": 1758801600,
            "category": "company",
        }
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("x-finnhub-token") == "test"  # token in header, not URL
        assert "finnhub.io" in str(request.url)
        return httpx.Response(200, content=json.dumps(payload).encode())

    inner = httpx.Client(
        transport=httpx.MockTransport(handler),
        headers={"User-Agent": "t", "X-Finnhub-Token": "test"},
    )
    client = HardenedHttpClient(
        user_agent="t", allowed_hosts=frozenset({"finnhub.io"}), rate_per_sec=1000, client=inner
    )
    articles = list(FinnhubNewsSource(client=client).get_news("NVDA"))
    assert len(articles) == 1
    assert articles[0].title == "NVIDIA unveils chip" and articles[0].publisher == "Reuters"
    assert articles[0].summary == "A short summary."  # no full body (LGL-004)


def test_news_provider_switch_is_independent_of_provider_mode(  # DR-004, SEC-001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.config import get_settings
    from app.providers.news import get_news_source
    from app.providers.news.mock import MockNewsSource

    assert isinstance(get_news_source(), MockNewsSource)  # the suite's default stays offline
    monkeypatch.setenv("NEWS_PROVIDER", "finnhub")
    monkeypatch.setenv("FINNHUB_API_KEY", "")
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="FINNHUB_API_KEY"):
            get_news_source()
        monkeypatch.setenv("FINNHUB_API_KEY", "test-key")
        get_settings.cache_clear()
        assert isinstance(get_news_source(), FinnhubNewsSource)  # PROVIDER_MODE is still mock
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
