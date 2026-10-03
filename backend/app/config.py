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

    # --- RAG retrieval pipeline (Phase 2c, §16, ADR-0003/0014) ---
    rag_candidate_top_n: int = Field(default=40)  # candidates per index before fusion (RAG-010)
    rag_rerank_top_k: int = Field(default=10)  # final evidence count after rerank (RAG-012)
    rag_rrf_k: int = Field(default=60)  # Reciprocal Rank Fusion constant (RAG-011)
    rag_rerank_enabled: bool = Field(default=True)  # off = fusion order only, for latency tests
    # Minimum top reranker score to proceed; below this the pipeline abstains (RAG-018). Tuned to
    # the LexicalReranker scale (ADR-0014): zero query-term overlap floors near 0.35, so 0.4
    # abstains on irrelevant hits while any real term overlap clears it. Re-tune per reranker.
    rag_sufficiency_min_score: float = Field(default=0.4)
    rag_max_chunks_per_document: int = Field(default=3)  # diversity cap (RAG-017)
    rag_context_token_budget: int = Field(default=6000)  # context-assembly budget (RAG-020)
    rag_max_tool_calls: int = Field(default=6)  # tool-call budget per question (RAG-031)
    rag_tool_timeout_s: float = Field(default=10.0)  # per-tool wall-clock timeout (RAG-031)
    # Model routing (RAG-050): cheap for classify/rewrite, strong reserved for Phase 3 synthesis.
    llm_model_cheap: str = Field(default="claude-haiku-4-5-20251001")
    llm_model_strong: str = Field(default="claude-sonnet-5-5")

    # --- Citation & verification (Phase 3a, §13/§14, ADR-0015) ---
    # Rounding tolerance for the deterministic numeric-match layer (CIT-005 L2): a cited number
    # matches a source value within this relative tolerance after unit normalization.
    citation_numeric_rel_tolerance: float = Field(default=0.01)
    # Lexical-entailment overlap thresholds (CIT-005 L3): ≥ supported, ≥ partial, else unsupported.
    citation_entail_supported_overlap: float = Field(default=0.6)
    citation_entail_partial_overlap: float = Field(default=0.3)
    # Policy for a "partially" entailed claim: "soften" (downgrade confidence) or "reject".
    citation_partial_policy: str = Field(default="soften")
    # Confidence weights (HAL-002); sum need not be 1 (score is clamped to [0,1]).
    citation_w_tier: float = Field(default=0.25)
    citation_w_sources: float = Field(default=0.2)
    citation_w_retrieval: float = Field(default=0.15)
    citation_w_entailment: float = Field(default=0.3)
    citation_w_agreement: float = Field(default=0.1)
    # Label thresholds (HAL-002): ≥ strong → "strongly_supported"; ≥ supported → "supported".
    citation_label_strong: float = Field(default=0.8)
    citation_label_supported: float = Field(default=0.55)


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
