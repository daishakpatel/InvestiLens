"""Run red-flag detection over stored filings (Phase 7e, FR-RF-007, ADR-0043).

Idempotent: an event already stored under the current taxonomy version is skipped, so this is safe
to re-run; after a taxonomy version bump it writes the new version's rows and leaves the old ones.

Usage:  cd backend && uv run python ../scripts/scan_red_flags.py [TICKER ...]
        (or `make redflags-backfill`)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select

from app.db import session_scope
from app.models import Company
from app.redflags.detect import scan_company


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tickers", nargs="*", help="companies to scan (default: all)")
    args = parser.parse_args(argv)
    with session_scope() as session:
        query = select(Company).order_by(Company.ticker)
        if args.tickers:
            query = query.where(Company.ticker.in_([t.upper() for t in args.tickers]))
        for company in session.scalars(query):
            print(f"{company.ticker}: {scan_company(session, company)}")


if __name__ == "__main__":
    main()
