"""Parse XBRL `companyfacts` JSON into `financial_facts` rows (Phase 1a, scope item 4).

Stores EVERY numeric fact, un-normalized (concept selection is Phase 1b). Each row keeps its own
`accession_number` and `filed_date` for point-in-time correctness (DR-023). Non-numeric or
malformed entries are skipped and counted, not stored, since `financial_facts.value` is numeric.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any


def _to_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _to_decimals(value: Any) -> int | None:
    return value if isinstance(value, int) else None  # "INF"/None -> None


def parse_companyfacts(
    company_id: int, companyfacts: dict[str, Any]
) -> tuple[list[dict[str, Any]], int]:
    """Return (rows, skipped_count). `rows` are mappings ready for bulk insert."""
    rows: list[dict[str, Any]] = []
    skipped = 0
    taxonomies = companyfacts.get("facts", {})
    for taxonomy, concepts in taxonomies.items():
        for concept, node in concepts.items():
            concept_tag = f"{taxonomy}:{concept}"
            for unit, entries in node.get("units", {}).items():
                for entry in entries:
                    try:
                        value = Decimal(str(entry["val"]))
                    except (InvalidOperation, KeyError, TypeError):
                        skipped += 1
                        continue
                    start = entry.get("start")
                    rows.append(
                        {
                            "company_id": company_id,
                            "accession_number": entry.get("accn", ""),
                            "concept_tag": concept_tag,
                            "context_id": entry.get("frame"),
                            "period_start": _to_date(start),
                            "period_end": _to_date(entry.get("end")),
                            "period_type": "duration" if start else "instant",
                            "dimensions": None,  # companyfacts is un-dimensioned
                            "value": value,
                            "unit": unit,
                            "decimals": _to_decimals(entry.get("decimals")),
                            "filed_date": _to_date(entry.get("filed")),
                            "is_amended": str(entry.get("form", "")).endswith("/A"),
                        }
                    )
    return rows, skipped
