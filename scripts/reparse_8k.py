"""Re-chunk 8-K filings with the current parser (Phase 7c, FR-EX-004, ADR-0041).

8-K items are full dotted codes since parser `sec-ingest-v2` ("5.02", not "5"), which changes
their chunk IDs. This re-parses only 8-K and 8-K/A filings that are not yet at the current
parser version, so it is safe to re-run: a second run finds every 8-K current and changes nothing.

Usage:  cd backend && uv run python ../scripts/reparse_8k.py [TICKER ...]   (or `make reparse-8k`)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select

from app.db import session_scope
from app.ingestion.documents.pipeline import parse_company_documents
from app.models import Company
from app.utils.storage import get_object_storage

EIGHT_K_FORMS = ("8-K", "8-K/A")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tickers", nargs="*", help="companies to re-parse (default: all)")
    args = parser.parse_args(argv)

    storage = get_object_storage()
    with session_scope() as session:
        query = select(Company).order_by(Company.ticker)
        if args.tickers:
            query = query.where(Company.ticker.in_([t.upper() for t in args.tickers]))
        for company in session.scalars(query):
            summary = parse_company_documents(
                session, company.id, storage=storage, filing_types=EIGHT_K_FORMS
            )
            print(f"{company.ticker}: {summary}")


if __name__ == "__main__":
    main()
