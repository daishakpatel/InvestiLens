"""Run price + corporate-action ingestion for seed companies (Phase 1d).

Sample prices by default (offline fixtures); PRICE_PROVIDER=tiingo uses Tiingo (needs
TIINGO_API_KEY) and replaces the company's sample history (ADR-0035). Companies must already exist
(run SEC ingestion first).

Usage:
    cd backend && uv run python ../scripts/ingest_prices.py NVDA AAPL JPM
    PRICE_PROVIDER=tiingo uv run python ../scripts/ingest_prices.py NVDA AAPL JPM AMD INTC
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db import _session_factory
from app.ingestion.prices import ingest_prices_for_tickers
from app.providers.prices import get_price_source


def main(tickers: list[str]) -> None:
    print(f"price source: {get_price_source().provider}; ingesting {', '.join(tickers)}")
    results = ingest_prices_for_tickers(_session_factory(), tickers)
    for ticker, counts in results.items():
        print(f"  {ticker}: {counts}")


if __name__ == "__main__":
    main(sys.argv[1:] or ["NVDA", "AAPL", "JPM"])
