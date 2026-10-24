"""Persist each proxy's structured pay figures (Tiers A and B, FR-GV-002..008, ADR-0045).

For every parsed DEF 14A (and a DEFA14A only if it carries a Summary Compensation Table), from the
raw HTML and the XBRL facts already ingested:

- the fiscal year the proxy covers, from its own content: the latest period of its
  Pay-Versus-Performance XBRL facts, else the latest year in its Summary Compensation Table. Never
  the filing date: JPMorgan files in April for the year ended the previous December;
- Tier A: Pay-Versus-Performance facts, five years each, cited `xbrl:<financial_facts.id>`;
- Tier B: Summary Compensation Table cells that validate, cited to the table chunk, and the CEO
  pay ratio if median pay x ratio is within 2% of the CEO's total, cited to its paragraph.

A rejected row is logged with its reason; a proxy with no year to tie it to stores nothing.
What each proxy yielded is recorded in `documents.metadata['proxy']` for the coverage report.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.governance.compensation import SctParse, find_pay_ratio, find_sct
from app.ingestion.documents.chunker import PARSER_VERSION
from app.ingestion.documents.ixbrl import IxValue, tagged_values, text_values
from app.models import Company, Document, Filing
from app.repositories import filings as filing_repo
from app.repositories import governance as repo
from app.utils.logging import get_logger, log_event
from app.utils.storage import get_object_storage

logger = get_logger(__name__)

# SEC `ecd` (Executive Compensation Disclosure) taxonomy elements, as tagged in companyfacts, and
# the net income the PvP table reports beside them (FR-GV-004).
PVP_CONCEPTS = {
    "ecd:PeoTotalCompAmt": "peo_total_comp",
    "ecd:PeoActuallyPaidCompAmt": "peo_actually_paid_comp",
    "ecd:NonPeoNeoAvgTotalCompAmt": "non_peo_neo_avg_total_comp",
    "ecd:NonPeoNeoAvgCompActuallyPaidAmt": "non_peo_neo_avg_actually_paid_comp",
    "ecd:TotalShareholderRtnAmt": "tsr",
    "ecd:PeerGroupTotalShareholderRtnAmt": "peer_group_tsr",
    "ecd:CoSelectedMeasureAmt": "company_selected_measure",
    "us-gaap:NetIncomeLoss": "net_income",
}
# Dollar values of a $100 investment, not money paid: unit "index" so they are never summed as pay.
_INDEX_KEYS = {"tsr", "peer_group_tsr"}

RawReader = Callable[[str], bytes]


@dataclass
class GovernanceCounts:
    proxies: int = 0
    facts: int = 0
    rejected_rows: int = 0


def proxy_fiscal_year(values: Sequence[IxValue], sct: SctParse) -> tuple[int, str] | None:
    """(fiscal year, how it was found) from the proxy's content (FR-GV-002, DR-GV-002).

    A fiscal year is named by the year it ends in, like the metrics (NVIDIA's year ended
    25 January 2026 is FY2026)."""
    ends = [
        v.context.period_end
        for v in values
        if v.concept.startswith("ecd:") and v.context.period_end is not None
    ]
    if ends:
        return max(ends).year, "pay_versus_performance_xbrl"
    if sct.rows:
        return max(r.year for r in sct.rows), "summary_compensation_table"
    return None


def _row(
    document: Document,
    fiscal_year: int,
    tier: str,
    key: str,
    value: Decimal,
    unit: str,
    source: str,
    *,
    person: str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    return {
        "company_id": document.company_id,
        "document_id": document.id,
        "fiscal_year": fiscal_year,
        "tier": tier,
        "fact_key": key,
        "person": person,
        "role": role,
        "value": value,
        "unit": unit,
        "source_id": source,
    }


def _pvp_rows(
    session: Session,
    filing: Filing,
    document: Document,
    values: Sequence[IxValue],
    table_source: str | None,
) -> list[dict[str, Any]]:
    """Pay Versus Performance by fiscal year: the ingested XBRL fact (`xbrl:<id>`) where
    companyfacts kept one, else the proxy's own inline XBRL value cited to its PvP table chunk
    (companyfacts keeps them only under the newest proxy for some filers, none for others)."""
    rows: dict[tuple[int, str], dict[str, Any]] = {}

    def add(year: int, key: str, value: Decimal, unit: str, source: str) -> None:
        unit = "index" if key in _INDEX_KEYS else unit
        rows.setdefault((year, key), _row(document, year, "pvp", key, value, unit, source))

    for fact in repo.facts_in_filing(
        session, filing.company_id, filing.accession_number, PVP_CONCEPTS
    ):
        if fact.period_end is not None and fact.value is not None:
            add(
                fact.period_end.year,
                PVP_CONCEPTS[fact.concept_tag],
                Decimal(fact.value),
                fact.unit or "USD",
                f"xbrl:{fact.id}",
            )
    for value in values if table_source else ():
        end = value.context.period_end
        if value.concept in PVP_CONCEPTS and not value.context.members and end is not None:
            add(end.year, PVP_CONCEPTS[value.concept], value.value, "USD", table_source or "")
    return list(rows.values())


def _chunks(
    session: Session, document: Document
) -> tuple[list[tuple[str, str]], dict[str, str], dict[str, str]]:
    """(text paragraphs in order, table_id -> paragraph_id, section key -> its first table)."""
    paragraphs: list[tuple[str, str]] = []
    tables: dict[str, str] = {}
    first_table: dict[str, str] = {}
    for chunk in filing_repo.get_filing_sections(session, document_id=document.id):
        if not chunk.paragraph_id:
            continue
        meta = chunk.chunk_metadata or {}
        if chunk.chunk_type == "table":
            tables[str(meta.get("table_id"))] = chunk.paragraph_id
            first_table.setdefault(str(meta.get("section_key")), chunk.paragraph_id)
        else:
            paragraphs.append((chunk.paragraph_id, chunk.text))
    return paragraphs, tables, first_table


def build_proxy(session: Session, filing: Filing, document: Document, html: str) -> tuple[int, int]:
    """Persist one proxy's Tier A/B figures. Returns (facts stored, rows rejected)."""
    values = tagged_values(html)
    peo_names = text_values(html, "ecd:PeoName")
    sct = find_sct(html, peo_names=peo_names)
    for reason in sct.rejected:
        log_event(
            logger,
            logging.WARNING,
            "governance.sct_row_rejected",
            accession=filing.accession_number,
            reason=reason,
        )
    year = proxy_fiscal_year(values, sct)
    measure = text_values(html, "ecd:CoSelectedMeasureName")
    info: dict[str, Any] = {
        "peo_names": peo_names,
        "sct_rejected": sct.rejected,
        "company_selected_measure": measure[0] if measure else None,
    }
    rows: list[dict[str, Any]] = []
    if year is not None:
        fiscal_year, basis = year
        info.update(fiscal_year=fiscal_year, fiscal_year_source=basis)
        paragraphs, tables, first_table = _chunks(session, document)
        pvp_table = first_table.get("proxy_pay_versus_performance")
        rows += _pvp_rows(session, filing, document, values, pvp_table)
        table = tables.get(f"t{sct.table_index:04d}") if sct.table_index is not None else None
        for comp in sct.rows if table else ():
            for key, amount in [*comp.components.items(), ("total", comp.total)]:
                rows.append(
                    _row(
                        document,
                        comp.year,
                        "sct",
                        key,
                        amount,
                        "USD",
                        table or "",
                        person=comp.person,
                        role=comp.role,
                    )
                )
        ceo = next(
            (r.total for r in sct.rows if r.role == "peo" and r.year == fiscal_year and table),
            None,
        )
        ratio = find_pay_ratio(paragraphs, ceo) if ceo is not None else None
        if ratio is not None:
            pid = ratio.paragraph_id
            rows.append(
                _row(document, fiscal_year, "pay_ratio", "ratio", ratio.ratio, "ratio_to_1", pid)
            )
            rows.append(
                _row(document, fiscal_year, "pay_ratio", "median_pay", ratio.median_pay, "USD", pid)
            )
        info["pay_ratio_status"] = (
            "found" if ratio else "no_ceo_total" if ceo is None else "not_validated"
        )
        info["sct_source_id"] = table
    stored = repo.replace_document_facts(session, document.id, rows)
    document.doc_metadata = {**(document.doc_metadata or {}), "proxy": info}
    return stored, len(sct.rejected)


def build_company_governance(
    session: Session, company: Company, *, read_raw: RawReader | None = None
) -> GovernanceCounts:
    """Rebuild every parsed proxy's structured pay figures for one company (idempotent)."""
    reader = read_raw or get_object_storage().get
    counts = GovernanceCounts()
    for filing, document in repo.proxy_filings(session, company.id, parser_version=PARSER_VERSION):
        sections = (document.doc_metadata or {}).get("proxy_sections", [])
        if filing.filing_type == "DEFA14A" and "summary_compensation_table" not in sections:
            continue  # supplemental material without the tables (FR-GV-003)
        try:
            html = reader(filing.raw_document_location or "").decode("utf-8", errors="ignore")
        except Exception as exc:  # one unreadable proxy never stops the rest
            log_event(
                logger,
                logging.WARNING,
                "governance.proxy_unreadable",
                accession=filing.accession_number,
                error=str(exc),
            )
            document.doc_metadata = {**(document.doc_metadata or {}), "proxy": {"unreadable": True}}
            continue
        stored, rejected = build_proxy(session, filing, document, html)
        counts.proxies += 1
        counts.facts += stored
        counts.rejected_rows += rejected
    return counts
