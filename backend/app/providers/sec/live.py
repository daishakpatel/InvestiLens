"""Live SEC EDGAR source (Phase 1a). Fetches over HTTPS with SEC fair-access controls."""

from __future__ import annotations

import html
import json
import re
from collections.abc import Sequence
from datetime import date
from typing import Any

from app.config import get_settings
from app.providers.sec.base import (
    CompanyMetadata,
    CompanyRef,
    ExhibitRef,
    FilingRef,
    SecSource,
    is_press_release_exhibit,
)
from app.utils.http import HardenedHttpClient
from app.utils.storage import ObjectStorage

# SEC-015: ingestion only ever fetches from these hosts.
ALLOWED_HOSTS = frozenset({"www.sec.gov", "data.sec.gov", "sec.gov"})
_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
# One document of a filing in its SGML header page: type, sequence, filename (FR-EX-005).
_HEADER_DOCUMENT = re.compile(
    r"<TYPE>([^\n<]+?)\s*\n<SEQUENCE>[^\n]*\n<FILENAME>([^\n<]+?)\s*\n", re.I
)


def parse_index_headers(page: str) -> list[tuple[str, str]]:
    """(document type, filename) for every document in a filing's `-index-headers.html`.

    EDGAR has no per-filing `-index.json`; the SGML header (HTML-escaped inside the page) is the
    one listing that names each document's type, so exhibits are found from it.
    """
    return [(t.strip(), f.strip()) for t, f in _HEADER_DOCUMENT.findall(html.unescape(page))]


def _refs(cik: str, block: dict[str, Any]) -> list[FilingRef]:
    """FilingRefs from one columnar submissions block (`filings.recent` or an older shard)."""
    count = len(block.get("accessionNumber", []))

    def column(name: str) -> list[Any]:
        return list(block.get(name) or [""] * count)

    refs: list[FilingRef] = []
    for form, accession, doc, filed, report, items, accepted in zip(
        column("form"),
        column("accessionNumber"),
        column("primaryDocument"),
        column("filingDate"),
        column("reportDate"),
        column("items"),
        column("acceptanceDateTime"),
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
                primary_doc_url=f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn}/{doc}",
                items=tuple(i.strip() for i in (items or "").split(",") if i.strip()) or None,
                accepted_at=accepted or None,
            )
        )
    return refs


class LiveSecSource(SecSource):
    def __init__(
        self, client: HardenedHttpClient | None = None, storage: ObjectStorage | None = None
    ) -> None:
        settings = get_settings()
        self._http = client or HardenedHttpClient(
            user_agent=settings.sec_user_agent,
            allowed_hosts=ALLOWED_HOSTS,
            rate_per_sec=settings.sec_rate_limit_per_sec,
        )
        self._storage = storage  # older submission pages are kept here when given

    def _json(self, url: str) -> dict[str, Any]:
        result: dict[str, Any] = json.loads(self._http.get_bytes(url))
        return result

    def company_tickers(self) -> Sequence[CompanyRef]:
        raw = json.loads(self._http.get_bytes(_COMPANY_TICKERS_URL))
        rows = raw.values() if isinstance(raw, dict) else raw
        return [
            CompanyRef(cik=f"{int(r['cik_str']):010d}", ticker=r["ticker"], title=r["title"])
            for r in rows
        ]

    def _submissions(self, cik: str) -> dict[str, Any]:
        return self._json(f"https://data.sec.gov/submissions/CIK{cik}.json")

    def company_metadata(self, cik: str) -> CompanyMetadata:
        sub = self._submissions(cik)
        sic = str(sub["sic"]).strip() if sub.get("sic") else None
        exchanges = sub.get("exchanges") or []
        fye = sub.get("fiscalYearEnd") or ""  # "MMDD"
        fye_fmt = f"{fye[:2]}-{fye[2:]}" if len(fye) == 4 and fye.isdigit() else None
        return CompanyMetadata(
            name=sub.get("name") or None,
            sic_code=sic,
            industry=sub.get("sicDescription") or None,
            exchange=exchanges[0] if exchanges else None,
            fiscal_year_end=fye_fmt,
        )

    def list_filings(self, cik: str, *, since: date | None = None) -> Sequence[FilingRef]:
        filings = self._submissions(cik)["filings"]
        refs = _refs(cik, filings["recent"])
        if since is not None:
            # Prolific filers (JPM files thousands of prospectuses) push 10-Ks out of the recent
            # block; older pages are fetched only while they reach back to `since` (FR-EX-011).
            for shard in filings.get("files") or []:
                if date.fromisoformat(shard["filingTo"]) >= since:
                    refs.extend(_refs(cik, self._shard(shard)))
        unique = {r.accession_number: r for r in refs}  # a shard may overlap the recent block
        return sorted(unique.values(), key=lambda r: r.filing_date, reverse=True)

    def _shard(self, shard: dict[str, Any]) -> dict[str, Any]:
        """One older submissions page. Its filings never change, so it is read from SEC once;
        the key carries the page's range and count, so a page SEC re-cuts is fetched again."""
        url = f"https://data.sec.gov/submissions/{shard['name']}"
        if self._storage is None:
            return self._json(url)
        key = (
            f"sec/submissions/{shard['name']}.{shard.get('filingFrom')}."
            f"{shard.get('filingTo')}.{shard.get('filingCount')}"
        )
        if self._storage.exists(key):
            cached: dict[str, Any] = json.loads(self._storage.get(key))
            return cached
        data = self._http.get_bytes(url)
        page: dict[str, Any] = json.loads(data)  # parse before storing: never cache a bad page
        self._storage.put(key, data)
        return page

    def companyfacts(self, cik: str) -> dict[str, Any]:
        return self._json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")

    def fetch_document(self, ref: FilingRef) -> bytes:
        return self._http.get_bytes(ref.primary_doc_url)

    def list_exhibits(self, filing: FilingRef) -> Sequence[ExhibitRef]:
        folder = filing.primary_doc_url.rsplit("/", 1)[0]
        page = self._http.get_bytes(f"{folder}/{filing.accession_number}-index-headers.html")
        wanted = [
            (t, f)
            for t, f in parse_index_headers(page.decode("utf-8", errors="ignore"))
            if is_press_release_exhibit(t)
        ]
        if not wanted:
            return []
        listing = self._json(f"{folder}/index.json")["directory"]["item"]
        sizes = {i["name"]: int(i["size"]) for i in listing if str(i.get("size", "")).isdigit()}
        return [
            ExhibitRef(
                filing_accession=filing.accession_number,
                exhibit_type=exhibit_type.upper(),
                filename=filename,
                url=f"{folder}/{filename}",
                size_bytes=sizes.get(filename),
            )
            for exhibit_type, filename in wanted
        ]

    def fetch_exhibit(self, exhibit: ExhibitRef) -> bytes:
        return self._http.get_bytes(exhibit.url)
