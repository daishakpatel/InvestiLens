"""Mock SEC source backed by frozen fixtures (Phase 0d/1a). Fully offline (DR-004)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any

from app.providers.mocks._fixtures import (
    company_reference,
    fixture_gzip_bytes,
    load_json,
)
from app.providers.sec.base import (
    CompanyMetadata,
    CompanyRef,
    ExhibitRef,
    FilingRef,
    SecSource,
    is_press_release_exhibit,
)

_CIK_TO_DIR = {"0001045810": "nvda", "0000320193": "aapl", "0000019617": "jpm"}


class MockSecSource(SecSource):
    def company_tickers(self) -> Sequence[CompanyRef]:
        return [
            CompanyRef(cik=row["cik"], ticker=row["ticker"], title=row["name"])
            for row in company_reference().values()
        ]

    def _dir(self, cik: str) -> str | None:
        return _CIK_TO_DIR.get(cik.zfill(10))

    def _manifest(self, cik: str) -> list[dict[str, Any]]:
        slug = self._dir(cik)
        return [] if slug is None else list(load_json(slug, "filings_manifest.json")["filings"])

    def list_filings(self, cik: str, *, since: date | None = None) -> Sequence[FilingRef]:
        # The fixture manifest is one page, so `since` has nothing older to reach for.
        return [
            FilingRef(
                cik=cik.zfill(10),
                form=f["form"],
                accession_number=f["accession_number"],
                primary_document=f["primary_document"],
                filing_date=f["filing_date"],
                report_date=f.get("report_date"),
                primary_doc_url=f["url"],
                items=tuple(f["items"]) if f.get("items") else None,
                local_file=f["local_file"],
                accepted_at=f.get("accepted_at"),
            )
            for f in self._manifest(cik)
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

    def list_exhibits(self, filing: FilingRef) -> Sequence[ExhibitRef]:
        slug = self._dir(filing.cik)
        entry = next(
            (
                f
                for f in self._manifest(filing.cik)
                if f["accession_number"] == filing.accession_number
            ),
            {},
        )
        return [
            ExhibitRef(
                filing_accession=filing.accession_number,
                exhibit_type=e["exhibit_type"],
                filename=e["filename"],
                url=e["url"],
                size_bytes=e.get("size_bytes"),
                local_file=f"{slug}/{e['local_file']}",  # "<company dir>/<fixture name>"
            )
            for e in entry.get("exhibits", [])
            if is_press_release_exhibit(e["exhibit_type"])
        ]

    def fetch_exhibit(self, exhibit: ExhibitRef) -> bytes:
        if exhibit.local_file is None or "/" not in exhibit.local_file:
            raise FileNotFoundError(f"no fixture exhibit {exhibit.filename}")
        slug, name = exhibit.local_file.split("/", 1)
        return fixture_gzip_bytes(slug, f"{name}.gz")
