"""Build canonical financial_metrics from ingested facts (Phase 1b).

Usage:  cd backend && uv run python ../scripts/build_metrics.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select

from app.comparison.peers import refresh_default_peer_set
from app.db import session_scope
from app.finance.builder import build_company_metrics
from app.finance.footnote_builder import build_company_footnotes
from app.finance.quality_builder import build_company_earnings_quality
from app.finance.ratio_builder import build_company_ratios
from app.finance.valuation_builder import build_company_valuation
from app.finance.valuation_history import build_valuation_history
from app.guidance.builder import build_company_guidance
from app.models import Company


def main() -> None:
    with session_scope() as session:
        companies = list(session.scalars(select(Company).order_by(Company.ticker)))
        for company in companies:
            counts = build_company_metrics(session, company)
            ratios = build_company_ratios(session, company)
            valuation = build_company_valuation(session, company)
            quality = build_company_earnings_quality(session, company)
            footnotes = build_company_footnotes(session, company)
            history = build_valuation_history(session, company)
            guided = build_company_guidance(session, company)  # outcomes against new actuals
            print(
                f"{company.ticker}: {counts}, derived_ratios={ratios}, valuation={valuation}, "
                f"earnings_quality={quality}, footnotes={footnotes}, valuation_history={history}, "
                f"guidance_outcomes={guided}"
            )
        # Default peer sets compare market caps, so they are drawn once every company's is fresh.
        for company in companies:
            refresh_default_peer_set(session, company)
            print(f"{company.ticker}: default peer set refreshed")


if __name__ == "__main__":
    main()
