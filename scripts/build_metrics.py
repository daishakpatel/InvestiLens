"""Build canonical financial_metrics from ingested facts (Phase 1b).

Usage:  cd backend && uv run python ../scripts/build_metrics.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select

from app.db import session_scope
from app.finance.builder import build_company_metrics
from app.finance.quality_builder import build_company_earnings_quality
from app.finance.ratio_builder import build_company_ratios
from app.finance.valuation_builder import build_company_valuation
from app.models import Company


def main() -> None:
    with session_scope() as session:
        companies = list(session.scalars(select(Company).order_by(Company.ticker)))
        for company in companies:
            counts = build_company_metrics(session, company)
            ratios = build_company_ratios(session, company)
            valuation = build_company_valuation(session, company)
            quality = build_company_earnings_quality(session, company)
            print(
                f"{company.ticker}: {counts}, derived_ratios={ratios}, valuation={valuation}, "
                f"earnings_quality={quality}"
            )


if __name__ == "__main__":
    main()
