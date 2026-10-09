"""Seed a demo-ready database for the seed tickers (Phase 5d, scope #12).

Runs the full ingestion pipeline in mock mode (offline, $0) for NVDA/AAPL/JPM — SEC filings,
prices, news, parsing, embeddings, metrics — so a fresh `make up && make seed` yields a populated
dashboard (NFR-012). With `--with-reports`, it also pre-generates a citation-backed research
report per company using the deterministic FakeLLM, so the hosted demo shows real-looking AI
reports at zero LLM spend. Swap in a real ANTHROPIC_API_KEY for genuine analysis.

Usage:
    cd backend && uv run python ../scripts/seed_demo.py --with-reports
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db import session_scope
from app.repositories import companies as company_repo
from app.tasks.ingestion import _refresh_one

_SEED = ["NVDA", "AAPL", "JPM"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed a demo-ready database")
    parser.add_argument("tickers", nargs="*", default=_SEED)
    parser.add_argument(
        "--with-reports", action="store_true", help="also pre-generate FakeLLM research reports"
    )
    args = parser.parse_args()
    tickers = args.tickers or _SEED

    for ticker in tickers:
        print(f"[seed] ingesting {ticker} (mock pipeline)…")
        _refresh_one(ticker)

    if args.with_reports:
        # FakeLLM lives with the tests (dev tooling only); it returns citation-verifiable output
        # so the demo's AI reports are non-empty and deterministic.
        from app.research.report import generate_report
        from tests.fakes import FakeLLM

        for ticker in tickers:
            print(f"[seed] generating demo report for {ticker} (FakeLLM)…")
            with session_scope() as session:
                company = company_repo.get_by_ticker(session, ticker)
                if company is not None:
                    generate_report(session, company, llm=FakeLLM())

    print("[seed] done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
