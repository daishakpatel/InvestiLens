"""Seed the database with placeholder rows so downstream agents can query immediately.

Inserts three companies — NVDA, AAPL, and JPM (JPM specifically exercises the "not
applicable for banks" sector rules later, DR-001) — plus one placeholder row in every table.
This is NOT real data (that arrives in Phase 1); values are obviously synthetic.

Idempotent: run it repeatedly; it upserts by natural key and refuses to duplicate.

Usage:  cd backend && uv run python ../scripts/seed.py
"""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

# Make `app` importable no matter the caller's CWD (this script lives outside the package).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import session_scope
from app.models import (
    Alert,
    ChatMessage,
    ChatSession,
    ClaimVerification,
    Company,
    CompanyIdentifier,
    CorporateAction,
    DataFreshness,
    DataQualityIssue,
    Document,
    DocumentChunk,
    EvalResult,
    EvalRun,
    Filing,
    FinancialFact,
    FinancialMetric,
    FiscalCalendar,
    IngestionDeadLetter,
    IngestionRun,
    InsiderTransaction,
    InstitutionalHolding,
    Job,
    LlmCall,
    News,
    PriceHistory,
    RefreshToken,
    ReportFeedback,
    ResearchReport,
    ResearchSource,
    RetrievalLog,
    User,
    Watchlist,
    WatchlistItem,
)

_NOW = datetime.now(UTC)
_TODAY = date(2026, 9, 29)

# (ticker, cik, name, exchange, sector, is_bank)
_SEED_COMPANIES = [
    ("NVDA", "0001045810", "NVIDIA Corporation", "NASDAQ", "Technology", False),
    ("AAPL", "0000320193", "Apple Inc.", "NASDAQ", "Technology", False),
    ("JPM", "0000019617", "JPMorgan Chase & Co.", "NYSE", "Financial Services", True),
]


def _get_or_create_company(
    session: Session, ticker: str, cik: str, name: str, exchange: str, sector: str
) -> Company:
    existing = session.scalar(select(Company).where(Company.cik == cik))
    if existing is not None:
        return existing
    company = Company(
        ticker=ticker,
        cik=cik,
        name=name,
        exchange=exchange,
        sector=sector,
        status="active",
        fiscal_year_end="12-31",
    )
    session.add(company)
    session.flush()  # assign company.id
    return company


def _seed_company_rows(session: Session, company: Company) -> None:
    """Add one placeholder row per table for a single company."""
    session.add_all(
        [
            CompanyIdentifier(
                company_id=company.id,
                identifier_type="ticker",
                identifier_value=company.ticker,
                is_primary=True,
            ),
            FiscalCalendar(
                company_id=company.id,
                fiscal_year=2025,
                fiscal_quarter=None,
                period_start=date(2025, 1, 1),
                period_end=date(2025, 12, 31),
                period_type="FY",
                weeks_in_period=52,
            ),
        ]
    )

    document = Document(
        company_id=company.id,
        document_type="filing",
        source_tier=1,
        title=f"{company.ticker} 10-K (placeholder)",
        content_hash=f"seed-{company.cik}-10k",
        parser_version="seed-0",
        published_at=_NOW,
    )
    session.add(document)
    session.flush()

    session.add_all(
        [
            Filing(
                document_id=document.id,
                company_id=company.id,
                filing_type="10-K",
                filing_date=_TODAY,
                period_end=date(2025, 12, 31),
                accession_number=f"seed-{company.cik}-0001",
                items=None,
            ),
            DocumentChunk(
                document_id=document.id,
                company_id=company.id,
                chunk_index=0,
                chunk_type="text",
                text="Placeholder chunk for seed data.",
                section="Item 7",
                section_path=["Item 7", "MD&A"],
                paragraph_id="p_0",
                char_start=0,
                char_end=31,
                tier=1,
                filing_type="10-K",
                filing_date=_TODAY,
                embedding=None,
                embedding_model=None,
                parser_version="seed-0",
                content_hash=f"seed-{company.cik}-chunk0",
            ),
            FinancialFact(
                company_id=company.id,
                accession_number=f"seed-{company.cik}-0001",
                concept_tag="us-gaap:Revenues",
                period_end=date(2025, 12, 31),
                period_type="duration",
                value=Decimal("1000000000.0000"),
                unit="USD",
                filed_date=_TODAY,
                is_amended=False,
            ),
            FinancialMetric(
                company_id=company.id,
                period="FY2025",
                fiscal_year=2025,
                period_end=date(2025, 12, 31),
                period_type="FY",
                metric_name="revenue",
                metric_value=Decimal("1000000000.00000000"),
                unit="USD",
                basis="gaap",
                is_derived=False,
                is_latest=True,
            ),
            PriceHistory(
                company_id=company.id,
                date=_TODAY,
                open=Decimal("100.0000"),
                high=Decimal("101.0000"),
                low=Decimal("99.0000"),
                close=Decimal("100.5000"),
                adj_close=Decimal("100.5000"),
                volume=1_000_000,
                provider="seed",
                ingested_at=_NOW,
            ),
            CorporateAction(
                company_id=company.id,
                action_type="dividend",
                ex_date=_TODAY,
                ratio_or_amount=Decimal("0.10000000"),
                provider="seed",
            ),
            News(
                document_id=None,
                company_id=company.id,
                title=f"{company.ticker} placeholder headline",
                publisher="seed",
                published_at=_NOW,
                content_hash=f"seed-{company.cik}-news0",
            ),
            InsiderTransaction(
                company_id=company.id,
                insider_name="Jane Doe",
                role="CFO",
                transaction_date=_TODAY,
                code="P",
                shares=100,
                price=Decimal("100.0000"),
                is_10b5_1=True,
                post_holdings=1_000,
            ),
            InstitutionalHolding(
                company_id=company.id,
                filer_cik="0000000000",
                filer_name="Seed Capital",
                period_end=date(2025, 12, 31),
                shares=10_000,
                value=Decimal("1000000.0000"),
                change_shares=0,
            ),
            DataFreshness(
                company_id=company.id,
                source="sec",
                last_success_at=_NOW,
                last_attempt_at=_NOW,
                status="fresh",
                message="seed",
            ),
            DataQualityIssue(
                company_id=company.id,
                metric_name="revenue",
                period="FY2025",
                issue_code="seed_placeholder",
                status="open",
            ),
        ]
    )


def _seed_ai_and_user_rows(session: Session, company: Company, user: User) -> None:
    """Report / chat / feedback rows that depend on both a company and a user."""
    report = ResearchReport(
        company_id=company.id,
        user_id=user.id,
        generated_at=_NOW,
        model="seed",
        prompt_version="seed-0",
        report_json={"summary": "placeholder"},
        data_version="seed-0",
        status="complete",
        cost_usd=Decimal("0.0000"),
        latency_ms=0,
    )
    session.add(report)
    session.flush()

    chat_session = ChatSession(user_id=user.id, company_id=company.id)
    session.add(chat_session)
    session.flush()

    message = ChatMessage(
        session_id=chat_session.id,
        role="assistant",
        content="Placeholder answer.",
        source_ids=["seed-src-0"],
        cost_usd=Decimal("0.0000"),
        latency_ms=0,
    )
    session.add(message)
    session.flush()

    watchlist = Watchlist(user_id=user.id, name="Seed watchlist")
    session.add(watchlist)
    session.flush()

    session.add_all(
        [
            ResearchSource(
                report_id=report.id,
                source_id="seed-src-0",
                source_type="text_chunk",
                citation_text="Placeholder citation.",
                tier=1,
            ),
            ClaimVerification(
                report_id=report.id,
                claim_id="c0",
                claim_text="Placeholder claim.",
                source_ids=["seed-src-0"],
                status="accepted",
                numeric_match=True,
            ),
            ReportFeedback(user_id=user.id, report_id=report.id, rating=1, reason="seed"),
            WatchlistItem(watchlist_id=watchlist.id, company_id=company.id, added_at=_NOW),
            Alert(
                user_id=user.id,
                company_id=company.id,
                alert_type="new_10k",
                channel="in_app",
                is_active=True,
            ),
        ]
    )


def _seed_operational_rows(session: Session, company: Company, user: User) -> None:
    """Operational rows that are not per-company-required but seeded once for completeness."""
    eval_run = EvalRun(name="seed", config_hash="seed", git_sha="seed", status="complete")
    session.add(eval_run)
    session.flush()
    session.add_all(
        [
            IngestionRun(
                source="sec",
                company_id=company.id,
                started_at=_NOW,
                ended_at=_NOW,
                status="success",
                counts={"documents": 1},
            ),
            IngestionDeadLetter(source="sec", payload_ref="seed", error="seed placeholder"),
            Job(
                job_type="seed",
                status="complete",
                progress=100,
                created_by=user.id,
                started_at=_NOW,
                ended_at=_NOW,
                attempts=1,
            ),
            LlmCall(
                request_id="seed",
                purpose="seed",
                model="seed",
                input_tokens=0,
                output_tokens=0,
                cost_usd=Decimal("0.0000"),
                latency_ms=0,
                status="ok",
            ),
            RetrievalLog(
                request_id="seed", query="seed", intent="seed", top_k=0, latency_ms=0, chunk_ids=[]
            ),
            EvalResult(run_id=eval_run.id, question_id="q0", metrics={"score": 1}),
        ]
    )


def _get_or_create_user(session: Session) -> User:
    email = "seed@investilens.local"
    existing = session.scalar(select(User).where(User.email == email))
    if existing is not None:
        return existing
    # Placeholder hash only — not a usable credential.
    user = User(
        email=email,
        password_hash="seed-not-a-real-hash",  # noqa: S106
        role="user",
        is_active=True,
        ai_budget_month_usd=Decimal("10.0000"),
    )
    session.add(user)
    session.flush()
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash="seed-token-hash",  # noqa: S106
            family_id="seed-family",
            issued_at=_NOW,
            expires_at=_NOW,
        )
    )
    return user


def seed_into(session: Session) -> int:
    """Insert seed data using the given session. Returns the number of companies seeded.

    Idempotent: returns 0 if any company already exists. The caller owns the transaction.
    """
    if session.scalar(select(Company).limit(1)) is not None:
        return 0
    user = _get_or_create_user(session)
    for ticker, cik, name, exchange, sector, _is_bank in _SEED_COMPANIES:
        company = _get_or_create_company(session, ticker, cik, name, exchange, sector)
        _seed_company_rows(session, company)
        _seed_ai_and_user_rows(session, company, user)
    # Operational rows only need one company reference.
    first = session.scalar(select(Company).order_by(Company.id))
    assert first is not None  # noqa: S101
    _seed_operational_rows(session, first, user)
    return len(_SEED_COMPANIES)


def seed() -> None:
    """Insert seed companies and placeholder rows in every table (idempotent)."""
    with session_scope() as session:
        count = seed_into(session)
    if count == 0:
        print("Seed data already present; nothing to do.")
    else:
        print(f"Seeded {count} companies with placeholder rows in every table.")


if __name__ == "__main__":
    seed()
