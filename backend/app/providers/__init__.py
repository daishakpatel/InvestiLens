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
    settings = get_settings()
    # LLM_PROVIDER picks the model on its own, so a real LLM can run over fixture data (ADR-0032).
    # The public demo replays recorded responses only, whatever else is set (NFR-ME-009).
    if settings.demo_mode or (settings.llm_provider or settings.provider_mode) == "mock":
        return MockLLMClient()
    from app.providers.gemini import GeminiLLMClient

    return GeminiLLMClient()


def get_embedding_client() -> EmbeddingClient:
    settings = get_settings()
    # EMBEDDING_PROVIDER picks the embedder on its own, like LLM_PROVIDER (ADR-0033).
    provider = settings.embedding_provider or (
        "mock" if settings.provider_mode == "mock" else "voyage"
    )
    if settings.demo_mode:  # the demo's fixtures are embedded with the offline embedder
        provider = "mock"
    if provider == "mock":
        return MockEmbeddingClient()
    if provider == "gemini":
        from app.providers.gemini import GeminiEmbeddingClient

        return GeminiEmbeddingClient()
    from app.providers.voyage import VoyageEmbeddingClient

    return VoyageEmbeddingClient()
