"""Live SEC EDGAR source (Phase 1a). Fetches over HTTPS with SEC fair-access controls."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from app.config import get_settings
from app.providers.sec.base import CompanyRef, FilingRef, SecSource
from app.utils.http import HardenedHttpClient

# SEC-015: ingestion only ever fetches from these hosts.
ALLOWED_HOSTS = frozenset({"www.sec.gov", "data.sec.gov", "sec.gov"})
_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"


class LiveSecSource(SecSource):
    def __init__(self, client: HardenedHttpClient | None = None) -> None:
        settings = get_settings()
        self._http = client or HardenedHttpClient(
            user_agent=settings.sec_user_agent,
            allowed_hosts=ALLOWED_HOSTS,
            rate_per_sec=settings.sec_rate_limit_per_sec,
        )

    def company_tickers(self) -> Sequence[CompanyRef]:
        raw = json.loads(self._http.get_bytes(_COMPANY_TICKERS_URL))
        rows = raw.values() if isinstance(raw, dict) else raw
        return [
            CompanyRef(cik=f"{int(r['cik_str']):010d}", ticker=r["ticker"], title=r["title"])
            for r in rows
        ]

    def list_filings(self, cik: str) -> Sequence[FilingRef]:
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        recent = json.loads(self._http.get_bytes(url))["filings"]["recent"]
        refs: list[FilingRef] = []
        for form, accession, doc, filed, report, items in zip(
            recent["form"],
            recent["accessionNumber"],
            recent["primaryDocument"],
            recent["filingDate"],
            recent["reportDate"],
            recent["items"],
            strict=True,
        ):
            accn = accession.replace("-", "")
            refs.append(
                FilingRef(
                    cik=cik,
                    form=form,
                    accession_number=accession,
                    primary_document=doc,
                    filing_date=filed,
                    report_date=report or None,
                    primary_doc_url=(
                        f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn}/{doc}"
                    ),
                    items=tuple(i.strip() for i in items.split(",") if i.strip()) or None,
                )
            )
        return refs

    def companyfacts(self, cik: str) -> dict[str, Any]:
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        result: dict[str, Any] = json.loads(self._http.get_bytes(url))
        return result

    def fetch_document(self, ref: FilingRef) -> bytes:
        return self._http.get_bytes(ref.primary_doc_url)
