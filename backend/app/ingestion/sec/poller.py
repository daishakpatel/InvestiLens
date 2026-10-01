"""New-filing poller (Phase 1a stub; wired to Celery Beat in Phase 5d).

For each watched company, discover accession numbers that are not yet in `filings`. The actual
scheduling/queueing is added with the background-jobs infrastructure; this provides the pure
detection function so it can be tested and reused now.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.providers.sec import SecSource, get_sec_source
from app.repositories.filings import filing_exists


def find_new_accessions(session: Session, cik: str, *, sec: SecSource | None = None) -> list[str]:
    """Return accession numbers available at EDGAR but not yet ingested."""
    sec = sec or get_sec_source()
    return [
        ref.accession_number
        for ref in sec.list_filings(cik)
        if not filing_exists(session, ref.accession_number)
    ]
