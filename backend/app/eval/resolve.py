"""Resolve a retrieved chunk's `document_id` to the golden set's doc-key (e.g. "nvda_10k").

Retrieval metrics are computed at document granularity, so both sides must agree on a key. The
golden set uses `{ticker_lower}_{form}` (form = 10k/10q/8k); here we derive the same key from the
database. Results are cached per run to avoid an N+1.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Company, Document, DocumentChunk

_FORM_MAP = {"10-K": "10k", "10-Q": "10q", "8-K": "8k"}


def _normalize_form(filing_type: str | None) -> str:
    if not filing_type:
        return "doc"
    return _FORM_MAP.get(filing_type.upper(), filing_type.lower().replace("-", ""))


class DocKeyResolver:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._cache: dict[int, str | None] = {}

    def key_for(self, document_id: int) -> str | None:
        if document_id in self._cache:
            return self._cache[document_id]
        row = self._session.execute(
            select(Company.ticker, DocumentChunk.filing_type)
            .join(Document, Document.company_id == Company.id)
            .join(DocumentChunk, DocumentChunk.document_id == Document.id)
            .where(Document.id == document_id)
            .limit(1)
        ).first()
        key = f"{row[0].lower()}_{_normalize_form(row[1])}" if row else None
        self._cache[document_id] = key
        return key
