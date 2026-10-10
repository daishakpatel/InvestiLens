"""Company + identifier persistence (idempotent). No business logic here (spec §19.4)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import Company, CompanyIdentifier


def get_by_ticker(session: Session, ticker: str) -> Company | None:
    """Look up a company by ticker (case-insensitive), company-scoped reads for the tool layer."""
    return session.scalar(select(Company).where(Company.ticker == ticker.upper()))


def get_many_by_ticker(session: Session, tickers: list[str]) -> dict[str, Company]:
    """Resolve several tickers at once (case-insensitive) → {UPPER ticker: Company} (no N+1)."""
    upper = [t.upper() for t in tickers]
    rows = session.scalars(select(Company).where(Company.ticker.in_(upper)))
    return {c.ticker.upper(): c for c in rows}


def list_active(session: Session) -> list[Company]:
    """All active companies, for peer-set candidate generation (§37.1)."""
    return list(
        session.scalars(select(Company).where(Company.status == "active").order_by(Company.ticker))
    )


def search(session: Session, q: str, *, limit: int) -> list[Company]:
    """Fuzzy company search by ticker or name (FR-001), case-insensitive, name-ordered.

    A ticker match (exact or prefix) ranks ahead of a name substring match so typing a ticker
    surfaces the company first; the caller turns this ordering into a relevance score.
    """
    like = f"%{q}%"
    ticker_prefix = f"{q.upper()}%"
    return list(
        session.scalars(
            select(Company)
            .where(Company.ticker.ilike(like) | Company.name.ilike(like))
            .order_by(
                Company.ticker.ilike(ticker_prefix).desc(),  # ticker hits first
                Company.name,
            )
            .limit(limit)
        )
    )


def upsert_company(
    session: Session,
    *,
    ticker: str,
    cik: str,
    name: str,
    exchange: str | None = None,
    sector: str | None = None,
    industry: str | None = None,
    sic_code: str | None = None,
    fiscal_year_end: str | None = None,
) -> int:
    """Insert or update a company by CIK; return its id (ING-001 idempotent).

    On conflict, profile fields (exchange/sector/industry/sic_code/fiscal_year_end) are only
    overwritten when a non-NULL value is supplied, so a metadata-less re-ingest never wipes an
    earlier enrichment (`COALESCE(excluded, existing)`).
    """
    values = {
        "ticker": ticker,
        "cik": cik,
        "name": name,
        "exchange": exchange,
        "sector": sector,
        "industry": industry,
        "sic_code": sic_code,
        "fiscal_year_end": fiscal_year_end,
    }
    insert_stmt = pg_insert(Company).values(**values)
    preserve = ("exchange", "sector", "industry", "sic_code", "fiscal_year_end")
    update_set = {
        col: (
            func.coalesce(insert_stmt.excluded[col], Company.__table__.c[col])
            if col in preserve
            else v
        )
        for col, v in values.items()
        if col != "cik"
    }
    stmt = insert_stmt.on_conflict_do_update(
        index_elements=[Company.cik], set_=update_set
    ).returning(Company.id)
    company_id: int = session.execute(stmt).scalar_one()
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
