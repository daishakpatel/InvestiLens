"""Parse & chunk ingested documents into document_chunks (Phase 2a; Phase 7c).

Reads raw HTML from object storage (run SEC ingestion first) and parses every filing, late-filing
notice and EX-99 exhibit not yet at the current parser version; current ones are skipped.
Re-parsing keeps the embedding of any chunk whose text is unchanged (ADR-0041).

Usage:  cd backend && uv run python ../scripts/parse_filings.py [TICKER ...]
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


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tickers", nargs="*", help="companies to parse (default: all)")
    args = parser.parse_args(argv)

    storage = get_object_storage()
    with session_scope() as session:
        query = select(Company).order_by(Company.ticker)
        if args.tickers:
            query = query.where(Company.ticker.in_([t.upper() for t in args.tickers]))
        for company in session.scalars(query):
            summary = parse_company_documents(session, company.id, storage=storage)
            print(f"{company.ticker}: {summary}")


if __name__ == "__main__":
    main()
