"""Mock SEC source backed by frozen fixtures (Phase 0d/1a). Fully offline (DR-004)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.providers.mocks._fixtures import (
    company_reference,
    fixture_gzip_bytes,
    load_json,
)
from app.providers.sec.base import CompanyMetadata, CompanyRef, FilingRef, SecSource

_CIK_TO_DIR = {"0001045810": "nvda", "0000320193": "aapl", "0000019617": "jpm"}


class MockSecSource(SecSource):
    def company_tickers(self) -> Sequence[CompanyRef]:
        return [
            CompanyRef(cik=row["cik"], ticker=row["ticker"], title=row["name"])
            for row in company_reference().values()
        ]

    def _dir(self, cik: str) -> str | None:
        return _CIK_TO_DIR.get(cik.zfill(10))

    def list_filings(self, cik: str) -> Sequence[FilingRef]:
        slug = self._dir(cik)
        if slug is None:
            return []
        manifest = load_json(slug, "filings_manifest.json")
        return [
            FilingRef(
                cik=cik.zfill(10),
                form=f["form"],
                accession_number=f["accession_number"],
                primary_document=f["primary_document"],
                filing_date=f["filing_date"],
                report_date=f.get("report_date"),
                primary_doc_url=f["url"],
                items=None,
                local_file=f["local_file"],
            )
            for f in manifest["filings"]
        ]

    def company_metadata(self, cik: str) -> CompanyMetadata:
        padded = cik.zfill(10)
        for row in company_reference().values():
            if row["cik"] == padded:
                return CompanyMetadata(
                    name=row.get("name"),
                    sic_code=row.get("sic"),
                    industry=row.get("industry"),
                    exchange=row.get("exchange"),
                    fiscal_year_end=row.get("fiscal_year_end"),
                )
        return CompanyMetadata()

    def companyfacts(self, cik: str) -> dict[str, Any]:
        slug = self._dir(cik)
        if slug is None:
            return {}
        result: dict[str, Any] = load_json(slug, "companyfacts.json.gz")
        return result

    def fetch_document(self, ref: FilingRef) -> bytes:
        slug = self._dir(ref.cik)
        if slug is None or ref.local_file is None:
            raise FileNotFoundError(f"no fixture document for {ref.accession_number}")
        return fixture_gzip_bytes(slug, f"{ref.local_file}.gz")
