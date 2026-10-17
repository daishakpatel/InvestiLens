"""Parse & chunk ingested filings into document_chunks (Phase 2a).

Reads raw filing HTML from object storage. Run SEC ingestion first.
Usage:  cd backend && uv run python ../scripts/parse_filings.py [TICKER ...]
With tickers, only those companies' filings are parsed. Re-parsing replaces a filing's chunks,
which drops their embeddings, so name the companies you mean.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select

from app.config import get_settings
from app.db import session_scope
from app.ingestion.documents.pipeline import parse_and_chunk
from app.models import Company, Filing
from app.utils.storage import FilesystemObjectStorage


def main(tickers: list[str]) -> None:
    storage = FilesystemObjectStorage(get_settings().storage_dir)
    with session_scope() as session:
        query = select(Filing).where(Filing.filing_type.in_(("10-K", "10-Q")))
        if tickers:
            query = query.join(Company, Company.id == Filing.company_id).where(
                Company.ticker.in_([t.upper() for t in tickers])
            )
        filings = list(session.scalars(query))
        for filing in filings:
            counts = parse_and_chunk(session, filing, storage=storage)
            print(f"  {filing.accession_number}: {counts}")


if __name__ == "__main__":
    main(sys.argv[1:])
