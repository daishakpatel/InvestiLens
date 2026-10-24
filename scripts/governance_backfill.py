"""Build governance data from stored proxy statements (Phase 7g, FR-GV-004/010, ADR-0045).

For each company: rebuilds the Pay-Versus-Performance and Summary Compensation Table figures of
every parsed proxy (deterministic, idempotent), then extracts the quoted board facts of its
latest three DEF 14A proxies with the configured LLM, skipping any already cached, so re-runs spend
nothing. `--no-llm` skips the extraction.

Usage:  cd backend && uv run python ../scripts/governance_backfill.py [--no-llm] [TICKER ...]
        (or `make governance-backfill`)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select

from app.db import session_scope
from app.governance.builder import build_company_governance
from app.governance.facts import extract_company_facts
from app.models import Company


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tickers", nargs="*", help="companies to process (default: all)")
    parser.add_argument("--no-llm", action="store_true", help="skip the Tier C extraction")
    args = parser.parse_args(argv)
    with session_scope() as session:
        query = select(Company).order_by(Company.ticker)
        if args.tickers:
            query = query.where(Company.ticker.in_([t.upper() for t in args.tickers]))
        for company in session.scalars(query):
            counts = build_company_governance(session, company)
            calls = 0 if args.no_llm else extract_company_facts(session, company)
            print(f"{company.ticker}: {counts}, extraction calls={calls}")


if __name__ == "__main__":
    main()
