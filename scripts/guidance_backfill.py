"""Extract company guidance from stored earnings releases and compare it with actuals (Phase 7i).

For each company: reads the outlook of its latest twelve EX-99.1 press releases with the
configured LLM, skipping any already cached, so re-runs spend nothing; then chains revisions and
recomputes every verified item's outcome (deterministic). `--no-llm` only recomputes outcomes.

Usage:  cd backend && uv run python ../scripts/guidance_backfill.py [--no-llm] [TICKER ...]
        (or `make guidance-backfill`)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select

from app.db import session_scope
from app.guidance.builder import build_company_guidance
from app.guidance.extract import extract_company_guidance
from app.models import Company


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tickers", nargs="*", help="companies to process (default: all)")
    parser.add_argument("--no-llm", action="store_true", help="skip extraction; outcomes only")
    args = parser.parse_args(argv)
    with session_scope() as session:
        query = select(Company).order_by(Company.ticker)
        if args.tickers:
            query = query.where(Company.ticker.in_([t.upper() for t in args.tickers]))
        for company in session.scalars(query):
            calls = 0 if args.no_llm else extract_company_guidance(session, company)
            items = build_company_guidance(session, company)
            print(f"{company.ticker}: extraction calls={calls}, verified items={items}")


if __name__ == "__main__":
    main()
