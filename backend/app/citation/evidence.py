"""Evidence items the verifier checks claims against (CIT-005).

An `EvidenceItem` bundles a backend-issued `SourceRecord` with the retrievable text the LLM saw and
its retrieval score. It exists because the typed `SourceRecord` variants don't all carry free text
(a table or earnings anchor doesn't), while numeric-match and entailment need something to read. The
evidence set passed per request is the single authority for ID validation (CIT-005 L1).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from app.schemas.sources import (
    DerivedMetricSource,
    SourceRecord,
    TableChunkSource,
    XbrlFactSource,
)


@dataclass
class EvidenceItem:
    source: SourceRecord
    text: str = ""
    retrieval_score: float = 0.5

    @property
    def source_id(self) -> str:
        return self.source.source_id

    @property
    def tier(self) -> int:
        return self.source.tier

    def searchable_text(self) -> str:
        """Everything a claim can be checked against: text + structured value + table labels."""
        parts: list[str] = [self.text or ""]
        src = self.source
        if isinstance(src, (XbrlFactSource, DerivedMetricSource)) and src.value is not None:
            parts.append(str(src.value))
        if isinstance(src, TableChunkSource):
            parts.extend(src.row_labels + src.col_labels + src.cell_refs)
        return " ".join(p for p in parts if p)

    def structured_values(self) -> list[Decimal]:
        """Exact backend values for the numeric-match 'derivable' path (xbrl/derived)."""
        src = self.source
        if isinstance(src, (XbrlFactSource, DerivedMetricSource)) and src.value is not None:
            return [src.value]
        return []


def index_evidence(items: Iterable[EvidenceItem]) -> dict[str, EvidenceItem]:
    """Build the per-request evidence set (source_id → item), the authority for ID validation."""
    return {item.source_id: item for item in items}
