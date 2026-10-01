"""Fetch and freeze real SEC fixtures for the seed companies (Phase 0d).

Downloads, for NVDA / AAPL / JPM, the XBRL `companyfacts` JSON and the primary HTML of the
latest 10-K, 10-Q, and 8-K, into `backend/tests/fixtures/<ticker>/`. This is a one-time
generator kept in the repo for reproducibility — the tests read the frozen files, never the
network.

Respects SEC fair access (LGL-002): a descriptive User-Agent and a request rate well under
5 req/s. This script does NOT use any personal email in the User-Agent.

Usage:  uv run python scripts/fetch_fixtures.py
"""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

# Generic contact per SEC fair-access policy; not a personal address.
USER_AGENT = "InvestiLens/0.1 fixtures (contact: dev@investilens.example)"
RATE_LIMIT_SECONDS = 0.3  # ~3 req/s, under SEC's 5 req/s ceiling (LGL-002)
FIXTURES = Path(__file__).resolve().parents[1] / "backend" / "tests" / "fixtures"

# (ticker, zero-padded 10-digit CIK)
COMPANIES = [
    ("nvda", "0001045810"),
    ("aapl", "0000320193"),
    ("jpm", "0000019617"),
]
WANTED_FORMS = ("10-K", "10-Q", "8-K")


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})  # noqa: S310
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (trusted SEC host)
        data: bytes = resp.read()
    time.sleep(RATE_LIMIT_SECONDS)
    return data


def _latest_filings(cik: str) -> list[dict[str, str]]:
    """Return the latest filing of each wanted form for a company."""
    sub = json.loads(_get(f"https://data.sec.gov/submissions/CIK{cik}.json"))
    recent = sub["filings"]["recent"]
    rows = zip(
        recent["form"],
        recent["accessionNumber"],
        recent["primaryDocument"],
        recent["filingDate"],
        recent["reportDate"],
        strict=True,
    )
    chosen: dict[str, dict[str, str]] = {}
    for form, accession, primary_doc, filing_date, report_date in rows:
        if form in WANTED_FORMS and form not in chosen:
            accn = accession.replace("-", "")
            chosen[form] = {
                "form": form,
                "accession_number": accession,
                "primary_document": primary_doc,
                "filing_date": filing_date,
                "report_date": report_date,
                "url": (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn}/{primary_doc}"),
            }
        if len(chosen) == len(WANTED_FORMS):
            break
    return list(chosen.values())


def fetch_company(ticker: str, cik: str) -> None:
    out = FIXTURES / ticker
    out.mkdir(parents=True, exist_ok=True)

    print(f"[{ticker}] companyfacts …")
    facts = _get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")
    (out / "companyfacts.json").write_bytes(facts)

    manifest: list[dict[str, str]] = []
    for filing in _latest_filings(cik):
        form_slug = filing["form"].replace("-", "").replace("/", "").lower()
        filename = f"{form_slug}.htm"
        print(f"[{ticker}] {filing['form']} {filing['filing_date']} -> {filename}")
        (out / filename).write_bytes(_get(filing["url"]))
        manifest.append({**filing, "local_file": filename})

    (out / "filings_manifest.json").write_text(
        json.dumps({"ticker": ticker.upper(), "cik": cik, "filings": manifest}, indent=2) + "\n"
    )


def main() -> None:
    for ticker, cik in COMPANIES:
        fetch_company(ticker, cik)
    print("Done. Fixtures written to", FIXTURES)


if __name__ == "__main__":
    main()
