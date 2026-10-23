"""Freeze the real SEC fixtures Phase 7c needs (exhibits, extra forms, a submissions shard).

Downloads, for NVIDIA, pinned filings that exercise the Phase 7c paths, gzips them into
`backend/tests/fixtures/nvda/`, and rewrites `filings_manifest.json` with their EDGAR metadata
(8-K items, acceptance time, exhibits). Also writes a trimmed `submissions` JSON and one older
shard under `backend/tests/fixtures/sec/` for the `filings.files[]` paging test. A one-time
generator kept for reproducibility: tests read the frozen files, never the network.

NVIDIA has never filed an NT 10-K / NT 10-Q and has no recent 8-K/A, so those three fixtures are
small synthetic documents, labelled as such in their text and in the manifest (`synthetic`).

Respects SEC fair access (LGL-002): a descriptive User-Agent and ~3 requests per second.

Usage:  uv run python scripts/fetch_phase7c_fixtures.py
"""

from __future__ import annotations

import gzip
import json
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.providers.sec.live import parse_index_headers

USER_AGENT = "AssayDesk/0.1 fixtures (contact: dev@assay-desk.example)"
RATE_LIMIT_SECONDS = 0.35
FIXTURES = Path(__file__).resolve().parents[1] / "backend" / "tests" / "fixtures"
CIK = "0001045810"
ARCHIVE = "https://www.sec.gov/Archives/edgar/data/1045810"

# (accession, local fixture name, exhibit types to freeze) — pinned so the fixtures are stable.
PINNED = [
    ("0001045810-26-000073", "8k_earnings.htm", ("EX-99.1", "EX-99.2")),  # Items 2.02, 9.01
    ("0001045810-26-000024", "8k_502.htm", ()),  # Items 5.02, 9.01 (EX-10.1 is ignored)
    ("0001045810-26-000036", "def14a.htm", ()),
    ("0001045810-26-000037", "defa14a.htm", ()),
]
SYNTHETIC = [
    # (form, accession, filing date, report date, local name, body)
    ("NT 10-K", "0000000000-26-900001", "2026-03-27", "2026-01-25", "nt10k.htm", "Form 12b-25"),
    ("NT 10-Q", "0000000000-26-900002", "2026-06-02", "2026-04-26", "nt10q.htm", "Form 12b-25"),
    ("8-K/A", "0000000000-26-900003", "2026-07-10", "2026-07-02", "8ka.htm", "Item 5.02"),
]


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})  # noqa: S310
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (trusted SEC host)
        data: bytes = resp.read()
    time.sleep(RATE_LIMIT_SECONDS)
    return data


def _write_gz(path: Path, data: bytes) -> None:
    path.write_bytes(gzip.compress(data, mtime=0))


def _documents(accession: str) -> list[tuple[str, str]]:
    """(type, filename) of every document in a filing, from its SGML header page."""
    folder = accession.replace("-", "")
    return parse_index_headers(_get(f"{ARCHIVE}/{folder}/{accession}-index-headers.html").decode())


def _sizes(accession: str) -> dict[str, int]:
    folder = accession.replace("-", "")
    listing = json.loads(_get(f"{ARCHIVE}/{folder}/index.json"))
    return {i["name"]: int(i["size"]) for i in listing["directory"]["item"] if i["size"]}


def _synthetic_html(form: str, body: str) -> bytes:
    return (
        "<html><body><p>SYNTHETIC TEST FIXTURE. NVIDIA Corporation has not filed this form; this "
        f"document only exercises {form} handling in Assay Desk's ingestion.</p>"
        f"<p>{form}</p><p>{body}</p></body></html>"
    ).encode()


def main() -> None:
    target = FIXTURES / "nvda"
    sub = json.loads(_get(f"https://data.sec.gov/submissions/CIK{CIK}.json"))
    recent = sub["filings"]["recent"]
    rows = {
        accession: dict(zip(recent.keys(), values, strict=True))
        for accession, values in zip(
            recent["accessionNumber"], zip(*recent.values(), strict=True), strict=True
        )
    }

    manifest_path = target / "filings_manifest.json"
    manifest: dict[str, Any] = json.loads(manifest_path.read_text())
    known = {f["accession_number"] for f in manifest["filings"]}
    # Real EDGAR metadata on the frozen filings too (items, acceptance time), as live reads it.
    for filing in manifest["filings"]:
        row = rows.get(filing["accession_number"])
        if row:
            filing["items"] = [i for i in row["items"].split(",") if i]
            filing["accepted_at"] = row["acceptanceDateTime"]

    for accession, local, wanted in PINNED:
        row = rows[accession]
        folder = accession.replace("-", "")
        primary = row["primaryDocument"]
        _write_gz(target / f"{local}.gz", _get(f"{ARCHIVE}/{folder}/{primary}"))
        exhibits = []
        if wanted:
            sizes = _sizes(accession)
            for exhibit_type, filename in _documents(accession):
                if exhibit_type in wanted:
                    name = f"{local.removesuffix('.htm')}_{exhibit_type.lower()}.htm"
                    _write_gz(target / f"{name}.gz", _get(f"{ARCHIVE}/{folder}/{filename}"))
                    exhibits.append(
                        {
                            "exhibit_type": exhibit_type,
                            "filename": filename,
                            "url": f"{ARCHIVE}/{folder}/{filename}",
                            "size_bytes": sizes.get(filename),
                            "local_file": name,
                        }
                    )
        if accession in known:
            continue
        manifest["filings"].append(
            {
                "form": row["form"],
                "accession_number": accession,
                "primary_document": primary,
                "filing_date": row["filingDate"],
                "report_date": row["reportDate"] or None,
                "accepted_at": row["acceptanceDateTime"],
                "items": [i for i in row["items"].split(",") if i],
                "url": f"{ARCHIVE}/{folder}/{primary}",
                "local_file": local,
                **({"exhibits": exhibits} if exhibits else {}),
            }
        )

    for form, accession, filed, report, local, body in SYNTHETIC:
        _write_gz(target / f"{local}.gz", _synthetic_html(form, body))
        if accession in known:
            continue
        manifest["filings"].append(
            {
                "form": form,
                "accession_number": accession,
                "primary_document": local,
                "filing_date": filed,
                "report_date": report,
                "accepted_at": f"{filed}T16:05:00.000Z",
                "items": ["5.02"] if form == "8-K/A" else [],
                "url": f"{ARCHIVE}/{accession.replace('-', '')}/{local}",
                "local_file": local,
                "synthetic": True,
            }
        )
    manifest["filings"].sort(key=lambda f: f["filing_date"], reverse=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    # Submissions paging fixture: the recent block trimmed to five filings, plus the first older
    # shard trimmed to its newest five, so the paging test runs on real EDGAR shapes.
    sec = FIXTURES / "sec"
    sec.mkdir(exist_ok=True)
    trimmed = {k: v[:5] for k, v in recent.items()}
    shard_meta = sub["filings"]["files"][0]
    shard = json.loads(_get(f"https://data.sec.gov/submissions/{shard_meta['name']}"))
    (sec / "submissions_nvda.json").write_text(
        json.dumps(
            {
                **{k: sub[k] for k in ("cik", "name")},
                "filings": {"recent": trimmed, "files": [shard_meta]},
            },
            indent=1,
        )
        + "\n"
    )
    (sec / "submissions_nvda_shard.json").write_text(
        json.dumps({k: v[:5] for k, v in shard.items()}, indent=1) + "\n"
    )
    print(f"wrote {len(PINNED)} real + {len(SYNTHETIC)} synthetic filings and a shard fixture")


if __name__ == "__main__":
    main()
