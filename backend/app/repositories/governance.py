"""exec_comp_facts persistence and proxy lookups (Phase 7g, ADR-0045).

Facts are replaced per proxy document in one statement, so a rebuild is idempotent (ING-001).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from app.ingestion.documents.sections import PROXY_FORMS
from app.models import Document, ExecCompFact, Filing, FinancialFact


def replace_document_facts(
    session: Session, document_id: int, rows: Iterable[dict[str, Any]]
) -> int:
    session.execute(delete(ExecCompFact).where(ExecCompFact.document_id == document_id))
    values = list(rows)
    if values:
        session.execute(insert(ExecCompFact), values)
    return len(values)


def facts_for_company(session: Session, company_id: int) -> list[ExecCompFact]:
    return list(
        session.scalars(
            select(ExecCompFact)
            .where(ExecCompFact.company_id == company_id)
            .order_by(ExecCompFact.fiscal_year, ExecCompFact.id)
        )
    )


def proxy_filings(
    session: Session, company_id: int, *, parser_version: str
) -> list[tuple[Filing, Document]]:
    """The company's parsed proxy filings (DEF 14A and DEFA14A), newest first."""
    rows = session.execute(
        select(Filing, Document)
        .join(Document, Document.id == Filing.document_id)
        .where(
            Filing.company_id == company_id,
            Filing.filing_type.in_(PROXY_FORMS),
            Document.parser_version == parser_version,
        )
        .order_by(Filing.filing_date.desc(), Filing.id.desc())
    )
    return [(filing, document) for filing, document in rows]


def facts_in_filing(
    session: Session, company_id: int, accession: str, concepts: Iterable[str]
) -> list[FinancialFact]:
    """XBRL facts a filing reported (companyfacts keeps each filing's own copy)."""
    return list(
        session.scalars(
            select(FinancialFact)
            .where(
                FinancialFact.company_id == company_id,
                FinancialFact.accession_number == accession,
                FinancialFact.concept_tag.in_(list(concepts)),
            )
            .order_by(FinancialFact.period_end, FinancialFact.id)
        )
    )
