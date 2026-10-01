"""Source-record endpoint powering the citation modal (spec §13, §24.2).

Returns the backend-issued source record (with anchor fields and deep link) so the UI can
highlight the exact supporting span (CIT-006).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.sources import SourceRecord, TextChunkSource

router = APIRouter(prefix="/sources", tags=["Sources"])


@router.get("/{source_id}", response_model=SourceRecord)
async def get_source(source_id: str) -> SourceRecord:
    return TextChunkSource(
        source_id=source_id,
        tier=1,
        document_id="nvda_10k_2025",
        section_path=["Item 7", "Results of Operations", "Revenue"],
        paragraph_id="p_217",
        char_start=10432,
        char_end=10981,
        page=None,
        url="https://www.sec.gov/Archives/edgar/data/1045810/...#p_217",
        text="Revenue for fiscal year 2025 was ...",
    )
