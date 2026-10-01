"""Application settings, loaded from the environment (see `.env.example`)."""

from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderMode = Literal["mock", "live"]


class Settings(BaseSettings):
    """Typed runtime configuration. Values come from environment variables / `.env`."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # postgresql+psycopg://user:pass@host:port/db  (ADR-0002)
    database_url: str = Field(
        default="postgresql+psycopg://investilens:devpassword@localhost:5432/investilens"
    )
    embedding_dimension: int = Field(default=1024)  # voyage-finance-2 (ADR-0010)
    # mock = frozen fixtures (offline, CI default, DR-004); live = real providers (later phases).
    provider_mode: ProviderMode = Field(default="mock")

    # --- SEC EDGAR ingestion (Phase 1a) ---
    # Descriptive UA with contact is mandatory (LGL-002). Not a personal address by default.
    sec_user_agent: str = Field(default="InvestiLens/0.1 (contact: dev@investilens.example)")
    sec_rate_limit_per_sec: float = Field(default=5.0)  # SEC fair-access ceiling (LGL-002)
    # Local object store root for raw filings (ING-008). S3/MinIO backend is Phase 5d (ADR-0012).
    storage_dir: str = Field(default=".storage")
    # Backfill policy (ING-002), configurable per deployment.
    backfill_10k_years: int = Field(default=5)
    backfill_10q_quarters: int = Field(default=12)
    backfill_8k_months: int = Field(default=24)

    # --- Prices: Tiingo (Phase 1d, ADR-0007) ---
    tiingo_api_key: str = Field(default="")  # required only when PROVIDER_MODE=live
    price_rate_limit_per_sec: float = Field(default=2.0)  # hourly cap handled by low volume+cache
    backfill_price_years: int = Field(default=5)  # 5y daily history for valuation bands

    # --- News: Finnhub (Phase 1e, ADR-0008) ---
    finnhub_api_key: str = Field(default="")  # required only when PROVIDER_MODE=live
    news_rate_limit_per_sec: float = Field(default=1.0)  # Finnhub free: 60/min
    news_backfill_days: int = Field(default=30)  # recent window; free tier has 1y history
    news_relevance_threshold: float = Field(default=0.3)  # min score shown by default
    news_dup_cosine_threshold: float = Field(default=0.9)  # near-duplicate clustering
    news_dup_window_days: int = Field(default=3)  # cluster only within this time window

    # --- Embeddings: Voyage AI (Phase 2b, ADR-0010/0013) ---
    voyage_api_key: str = Field(default="")  # required only when PROVIDER_MODE=live
    embedding_model: str = Field(default="voyage-finance-2")  # ADR-0010
    embedding_batch_size: int = Field(default=128)  # Voyage caps a request at 128 inputs (EMB-002)
    embedding_rate_limit_per_sec: float = Field(default=3.0)  # Voyage free tier: 3 req/sec
    # Blended $/1M tokens for cost logging (EMB-002). Voyage voyage-finance-2 list price; an
    # estimate used only for the `llm_calls` cost column, never for financial output.
    embedding_cost_per_1m_tokens: Decimal = Field(default=Decimal("0.12"))
    # HNSW query-time breadth (EMB-004). Higher = better recall, slower. Tuned in docs/rag.md.
    hnsw_ef_search: int = Field(default=100)


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
