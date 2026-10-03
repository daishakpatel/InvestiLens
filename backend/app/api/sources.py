"""Source-record endpoint powering the citation modal (spec §13, §24.2).

Resolves a backend-issued source_id to its full record, the text with the supporting span marked,
and a deep link where available (CIT-006). For a derived metric it also returns the lineage inputs
that drive the "How this was calculated" panel (CIT-003).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.citation.resolver import resolve_source
from app.db import get_db
from app.schemas.citations import SourceDetail

router = APIRouter(prefix="/sources", tags=["Sources"])

_DB = Depends(get_db)  # module-level so it is not a call in the argument default (ruff B008)


@router.get("/{source_id}", response_model=SourceDetail)
async def get_source(source_id: str, db: Session = _DB) -> SourceDetail:
    detail = resolve_source(db, source_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    return detail
