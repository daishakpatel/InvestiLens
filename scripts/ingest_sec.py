"""Run SEC ingestion for the seed companies (Phase 1a).

Uses `PROVIDER_MODE` to choose mock (frozen fixtures, offline) or live (real EDGAR). Populates
companies, identifiers, documents, filings, and financial_facts; safe to re-run (idempotent).

Usage:
    cd backend && uv run python ../scripts/ingest_sec.py NVDA AAPL JPM
    PROVIDER_MODE=live uv run python ../scripts/ingest_sec.py NVDA
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import get_settings
from app.db import _session_factory
from app.ingestion.sec import ingest_companies
from app.utils.storage import FilesystemObjectStorage


def main(tickers: list[str]) -> None:
    settings = get_settings()
    storage = FilesystemObjectStorage(settings.storage_dir)
    print(f"PROVIDER_MODE={settings.provider_mode}; ingesting {', '.join(tickers)}")
    result = ingest_companies(_session_factory(), tickers, storage=storage)
    for ticker, counts in result.per_company.items():
        print(f"  {ticker}: {counts.as_dict()}")
    for ticker, error in result.failures.items():
        print(f"  {ticker}: FAILED {error}")


if __name__ == "__main__":
    args = sys.argv[1:] or ["NVDA", "AAPL", "JPM"]
    main(args)
