"""Backfill company profile metadata (SIC/industry/exchange/FYE) from SEC submissions (Phase 6a).

Ingestion (Phase 1a) left these NULL; peer-set grouping (§37.1) and sector exposure (§37.2) need
them. This only touches profile columns — it does not re-download filings or facts — so it is cheap
and idempotent. Honors PROVIDER_MODE (live hits EDGAR; mock reads the fixture).

Usage:  cd backend && PROVIDER_MODE=live uv run python ../scripts/enrich_companies.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select

from app.config import get_settings
from app.db import session_scope
from app.finance.sic import sic_to_sector
from app.models import Company
from app.providers.sec import get_sec_source


def main() -> None:
    settings = get_settings()
    sec = get_sec_source()
    print(f"PROVIDER_MODE={settings.provider_mode}; enriching company metadata")
    with session_scope() as session:
        for company in session.scalars(select(Company).order_by(Company.ticker)):
            meta = sec.company_metadata(company.cik)
            company.sic_code = meta.sic_code or company.sic_code
            company.industry = meta.industry or company.industry
            company.exchange = meta.exchange or company.exchange
            company.fiscal_year_end = meta.fiscal_year_end or company.fiscal_year_end
            company.sector = sic_to_sector(meta.sic_code) or company.sector
            print(
                f"  {company.ticker}: sic={company.sic_code} sector={company.sector!r} "
                f"industry={company.industry!r} exch={company.exchange!r} "
                f"fye={company.fiscal_year_end}"
            )


if __name__ == "__main__":
    main()
