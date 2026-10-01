"""Mock FilingsProvider backed by frozen SEC fixtures (Phase 0d, DR-004)."""

from __future__ import annotations

from collections.abc import Sequence

from app.providers.base import FilingsProvider
from app.providers.mocks._fixtures import company_reference, load_json
from app.schemas.company import Company
from app.schemas.filings import FilingDetail, FilingSummary

_TICKER_DIRS = {"NVDA": "nvda", "AAPL": "aapl", "JPM": "jpm"}


class MockFilingsProvider(FilingsProvider):
    """Reads company reference data and filing manifests from `tests/fixtures/`."""

    async def resolve_company(self, ticker_or_cik: str) -> Company | None:
        key = ticker_or_cik.strip().upper()
        ref = company_reference()
        row = ref.get(key)
        if row is None:  # try CIK match
            padded = key.zfill(10) if key.isdigit() else key
            row = next((r for r in ref.values() if r["cik"] == padded), None)
        if row is None:
            return None
        return Company(**{k: v for k, v in row.items() if not k.startswith("_")})

    async def list_filings(
        self, cik: str, filing_type: str | None = None, limit: int = 50
    ) -> Sequence[FilingSummary]:
        ticker = next(
            (t for t, r in company_reference().items() if r["cik"] == cik.zfill(10)), None
        )
        if ticker is None:
            return []
        manifest = load_json(_TICKER_DIRS[ticker], "filings_manifest.json")
        summaries = [
            FilingSummary(
                filing_id=f"{ticker.lower()}_{f['form'].replace('-', '').lower()}",
                filing_type=f["form"],
                filing_date=f["filing_date"],
                period_end=f["report_date"],
                accession_number=f["accession_number"],
                primary_document_url=f["url"],
            )
            for f in manifest["filings"]
            if filing_type is None or f["form"] == filing_type
        ]
        return summaries[:limit]

    async def get_filing(self, accession_number: str) -> FilingDetail | None:
        for ticker, slug in _TICKER_DIRS.items():
            manifest = load_json(slug, "filings_manifest.json")
            for f in manifest["filings"]:
                if f["accession_number"] == accession_number:
                    return FilingDetail(
                        filing_id=f"{ticker.lower()}_{f['form'].replace('-', '').lower()}",
                        filing_type=f["form"],
                        filing_date=f["filing_date"],
                        period_end=f["report_date"],
                        accession_number=f["accession_number"],
                        primary_document_url=f["url"],
                        source_url=f["url"],
                        company_ticker=ticker,
                    )
        return None
