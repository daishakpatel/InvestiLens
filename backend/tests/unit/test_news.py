"""News ingestion unit tests (Phase 1e). Offline (spec §10.8, §15, LGL-004, ADR-0008)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

import httpx

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
