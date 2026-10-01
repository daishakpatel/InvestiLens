"""Run price + corporate-action ingestion for seed companies (Phase 1d).

PROVIDER_MODE=mock uses frozen fixtures (offline); PROVIDER_MODE=live uses Tiingo (needs
TIINGO_API_KEY). Companies must already exist (run SEC ingestion first).

Usage:
    cd backend && uv run python ../scripts/ingest_prices.py NVDA AAPL JPM
    PROVIDER_MODE=live TIINGO_API_KEY=... uv run python ../scripts/ingest_prices.py NVDA
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import get_settings
from app.db import _session_factory
from app.ingestion.prices import ingest_prices_for_tickers


def main(tickers: list[str]) -> None:
    mode = get_settings().provider_mode
    print(f"PROVIDER_MODE={mode}; ingesting prices for {', '.join(tickers)}")
    results = ingest_prices_for_tickers(_session_factory(), tickers)
    for ticker, counts in results.items():
        print(f"  {ticker}: {counts}")


if __name__ == "__main__":
    main(sys.argv[1:] or ["NVDA", "AAPL", "JPM"])
