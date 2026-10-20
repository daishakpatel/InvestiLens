"""Run news ingestion for seed companies (Phase 1e).

NEWS_PROVIDER (or PROVIDER_MODE when unset) picks the source: mock uses frozen fixtures (offline),
finnhub/live uses Finnhub (needs FINNHUB_API_KEY, ADR-0038). Companies must already exist (run
SEC ingestion first).

Usage:
    cd backend && uv run python ../scripts/ingest_news.py NVDA AAPL JPM
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import get_settings
from app.db import _session_factory
from app.ingestion.news import ingest_news_for_tickers


def main(tickers: list[str]) -> None:
    settings = get_settings()
    source = settings.news_provider or settings.provider_mode
    print(f"news source={source}; ingesting news for {', '.join(tickers)}")
    for ticker, counts in ingest_news_for_tickers(_session_factory(), tickers).items():
        print(f"  {ticker}: {counts}")


if __name__ == "__main__":
    main(sys.argv[1:] or ["NVDA", "AAPL", "JPM"])
