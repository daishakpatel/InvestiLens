"""Provider factory: returns mock or live implementations per `PROVIDER_MODE` (DR-004).

Mock is the default and the CI default (offline). Live implementations arrive in later phases;
until then requesting them raises, loudly, rather than silently falling back.
"""

from __future__ import annotations

from app.config import get_settings
from app.providers.base import (
    EmbeddingClient,
    FilingsProvider,
    LLMClient,
    NewsProvider,
    PriceProvider,
)
from app.providers.mocks.embeddings import MockEmbeddingClient
from app.providers.mocks.filings import MockFilingsProvider
from app.providers.mocks.llm import MockLLMClient
from app.providers.mocks.news import MockNewsProvider
from app.providers.mocks.prices import MockPriceProvider


def _live_unavailable(name: str) -> RuntimeError:
    return RuntimeError(f"Live {name} is not implemented yet; run with PROVIDER_MODE=mock.")


def get_filings_provider() -> FilingsProvider:
    if get_settings().provider_mode == "mock":
        return MockFilingsProvider()
    raise _live_unavailable("FilingsProvider")


def get_price_provider() -> PriceProvider:
    if get_settings().provider_mode == "mock":
        return MockPriceProvider()
    raise _live_unavailable("PriceProvider")


def get_news_provider() -> NewsProvider:
    if get_settings().provider_mode == "mock":
        return MockNewsProvider()
    raise _live_unavailable("NewsProvider")


def get_llm_client() -> LLMClient:
    if get_settings().provider_mode == "mock":
        return MockLLMClient()
    raise _live_unavailable("LLMClient")


def get_embedding_client() -> EmbeddingClient:
    if get_settings().provider_mode == "mock":
        return MockEmbeddingClient()
    raise _live_unavailable("EmbeddingClient")
