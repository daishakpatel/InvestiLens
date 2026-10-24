"""Footnote endpoints (Phase 7f, FR-FN-010/011, ADR-0044).

Read-only. `/notes` lists a 10-K's (or 10-Q's) notes with their category and cached AI summary;
`/footnote-facts` returns the XBRL facts by category. A summary that has not been generated yet is
`pending`: these handlers never call a model.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.companies import _resolve
from app.api.filings import to_summary
from app.db import get_db
from app.footnotes import service
from app.footnotes.summary import SUMMARISED_CATEGORIES
from app.ingestion.documents.chunker import PARSER_VERSION
from app.models import Document
from app.repositories import filings as filing_repo
from app.schemas.footnotes import FootnoteFactsResponse, NotesResponse

router = APIRouter(tags=["Footnotes"])

_DB = Depends(get_db, scope="function")
_FILING = Query(default=None, description="A 10-K or 10-Q of this company; default the latest 10-K")


@router.get("/companies/{ticker}/notes", response_model=NotesResponse)
def list_notes(ticker: str, filing_id: int | None = _FILING, db: Session = _DB) -> NotesResponse:
    company = _resolve(db, ticker)
    if filing_id is None:
        filing = filing_repo.get_latest_filing(
            db, company_id=company.id, filing_type="10-K", parser_version=PARSER_VERSION
        )
    else:
        filing = filing_repo.get_filing(db, filing_id)
    if filing is None or filing.company_id != company.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no parsed 10-K or 10-Q for this company")
    if not filing.filing_type.startswith(("10-K", "10-Q")):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "only 10-K and 10-Q have notes")
    document = db.get(Document, filing.document_id)
    stored = service.stored_notes(document)
    return NotesResponse(
        company_ticker=company.ticker,
        filing=to_summary(filing),
        taxonomy=stored["taxonomy"],
        low_confidence=stored["low_confidence"],
        summarised_categories=list(SUMMARISED_CATEGORIES),
        notes=service.note_items(document) if document else [],
    )


@router.get("/companies/{ticker}/footnote-facts", response_model=FootnoteFactsResponse)
def footnote_facts(ticker: str, db: Session = _DB) -> FootnoteFactsResponse:
    return service.footnote_facts(db, _resolve(db, ticker))
