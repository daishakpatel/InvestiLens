"""Parse & chunk ingested filings into document_chunks (Phase 2a).

Reads raw filing HTML from object storage. Run SEC ingestion first.
Usage:  cd backend && uv run python ../scripts/parse_filings.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select

from app.config import get_settings
from app.db import session_scope
from app.ingestion.documents.pipeline import parse_and_chunk
from app.models import Filing
from app.utils.storage import FilesystemObjectStorage


def main() -> None:
    storage = FilesystemObjectStorage(get_settings().storage_dir)
    with session_scope() as session:
        filings = list(session.scalars(select(Filing).where(Filing.filing_type == "10-K")))
        for filing in filings:
            counts = parse_and_chunk(session, filing, storage=storage)
            print(f"  {filing.accession_number}: {counts}")


if __name__ == "__main__":
    main()
