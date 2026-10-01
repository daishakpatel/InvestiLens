"""News ingestion pipeline (Phase 1e)."""

from app.ingestion.news.pipeline import NewsCounts, ingest_news, ingest_news_for_tickers

__all__ = ["NewsCounts", "ingest_news", "ingest_news_for_tickers"]
