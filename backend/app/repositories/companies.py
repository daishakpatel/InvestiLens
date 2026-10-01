"""Company + identifier persistence (idempotent). No business logic here (spec §19.4)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import Company, CompanyIdentifier


def upsert_company(
    session: Session,
    *,
    ticker: str,
    cik: str,
    name: str,
    exchange: str | None = None,
    sector: str | None = None,
    industry: str | None = None,
    fiscal_year_end: str | None = None,
) -> int:
    """Insert or update a company by CIK; return its id (ING-001 idempotent)."""
    stmt = (
        pg_insert(Company)
        .values(
            ticker=ticker,
            cik=cik,
            name=name,
            exchange=exchange,
            sector=sector,
            industry=industry,
            fiscal_year_end=fiscal_year_end,
        )
        .on_conflict_do_update(
            index_elements=[Company.cik],
            set_={
                "ticker": ticker,
                "name": name,
                "exchange": exchange,
                "sector": sector,
                "industry": industry,
                "fiscal_year_end": fiscal_year_end,
            },
        )
        .returning(Company.id)
    )
    company_id = session.execute(stmt).scalar_one()
    return int(company_id)


def upsert_identifier(
    session: Session,
    *,
    company_id: int,
    identifier_type: str,
    identifier_value: str,
    is_primary: bool = False,
) -> None:
    """Insert an identifier if the (company, type, value) triple is not already present."""
    exists = session.scalar(
        select(CompanyIdentifier.id).where(
            CompanyIdentifier.company_id == company_id,
            CompanyIdentifier.identifier_type == identifier_type,
            CompanyIdentifier.identifier_value == identifier_value,
        )
    )
    if exists is None:
        session.add(
            CompanyIdentifier(
                company_id=company_id,
                identifier_type=identifier_type,
                identifier_value=identifier_value,
                is_primary=is_primary,
            )
        )
