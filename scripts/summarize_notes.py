"""Summarise the narrative notes of each company's latest 10-K (Phase 7f, FR-FN-009, ADR-0044).

Only revenue recognition, commitments and contingencies, and segments are summarised, one model
call per note, cached on the document under (note, prompt version, model). Already-cached notes
are skipped, so this is safe to re-run; it spends nothing once everything is cached. Uses the
configured LLM (`LLM_PROVIDER`); in mock mode it caches offline stubs labelled "mock".

Usage:  cd backend && uv run python ../scripts/summarize_notes.py [TICKER ...]
        (or `make footnote-summaries`)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select

from app.db import session_scope
from app.footnotes.summary import summarize_company_notes
from app.models import Company


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tickers", nargs="*", help="companies to summarise (default: all)")
    args = parser.parse_args(argv)
    with session_scope() as session:
        query = select(Company).order_by(Company.ticker)
        if args.tickers:
            query = query.where(Company.ticker.in_([t.upper() for t in args.tickers]))
        for company in session.scalars(query):
            print(f"{company.ticker}: {summarize_company_notes(session, company)} notes summarised")


if __name__ == "__main__":
    main()
