"""Dev-stack helper for the thesis Playwright spec (Phase 7k). Never run against production.

Uses a throwaway company (ticker ZZTH) so the user's real data is never touched:

  setup                creates ZZTH with two TTM gross-margin rows (71%, 72%)
  alert --email E      gives user E a `thesis_trigger` alert on ZZTH (watermark: now)
  cross                stores a new TTM row at 66% and runs the real thesis evaluator
  dispatch             runs one real alert dispatch tick (the 5-minute beat job)
  teardown             deletes ZZTH and everything hanging off it (theses, KPIs, metrics, alert)

Run from `backend/`: `uv run python ../scripts/e2e_thesis.py setup`.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.alerts.dispatch import check_and_dispatch
from app.db import session_scope
from app.models import Alert, Company, FinancialMetric, User
from app.thesis.links import refresh_company_theses

TICKER = "ZZTH"
_ROWS = (
    ("TTM-Q1-FY2026", 1, date(2025, 4, 30), "0.71"),
    ("TTM-Q2-FY2026", 2, date(2025, 7, 31), "0.72"),
)


def _row(company: Company, period: str, quarter: int, end: date, value: str) -> FinancialMetric:
    return FinancialMetric(
        company_id=company.id,
        period=period,
        fiscal_year=2026,
        fiscal_quarter=quarter,
        period_end=end,
        period_type="TTM",
        metric_name="gross_margin",
        metric_value=Decimal(value),
        unit="ratio",
        basis="gaap",
        is_derived=True,
        source_id=f"derived:{TICKER}:gross_margin:{period}",
        as_reported_accession="derived",
        is_latest=True,
    )


def _company(session: Session) -> Company | None:
    return session.scalar(select(Company).where(Company.ticker == TICKER))


def setup() -> None:
    with session_scope() as session:
        if _company(session) is not None:
            return
        company = Company(
            ticker=TICKER, cik="0009999990", name="Thesis E2E Corp", sector="Technology"
        )
        session.add(company)
        session.flush()
        session.add_all(_row(company, *row) for row in _ROWS)


def alert(email: str) -> None:
    with session_scope() as session:
        company = _company(session)
        user = session.scalar(select(User).where(User.email == email))
        if company is None or user is None:
            raise SystemExit("run setup first, and sign up the user")
        session.add(
            Alert(user_id=user.id, company_id=company.id, event_type="thesis_trigger", params={})
        )


def cross() -> None:
    with session_scope() as session:
        company = _company(session)
        if company is None:
            raise SystemExit("run setup first")
        session.add(_row(company, "TTM-Q3-FY2026", 3, date(2025, 10, 31), "0.66"))
        session.flush()
        print(f"thesis events added: {refresh_company_theses(session, company)}")


def dispatch() -> None:
    with session_scope() as session:
        print(f"notifications: {check_and_dispatch(session)}")


def teardown() -> None:
    with session_scope() as session:
        company = _company(session)
        if company is not None:
            session.execute(delete(Alert).where(Alert.company_id == company.id))
            session.execute(delete(Company).where(Company.id == company.id))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("step", choices=["setup", "alert", "cross", "dispatch", "teardown"])
    parser.add_argument("--email", help="the signed-up user (alert step)")
    args = parser.parse_args()
    if args.step == "alert":
        if not args.email:
            parser.error("alert needs --email")
        alert(args.email)
    else:
        {"setup": setup, "cross": cross, "dispatch": dispatch, "teardown": teardown}[args.step]()


if __name__ == "__main__":
    main()
