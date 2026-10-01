"""Unit tests for SEC ingestion helpers (offline; fixtures only)."""

from __future__ import annotations

from datetime import date

from app.config import Settings
from app.ingestion.sec.items import parse_8k_items
from app.ingestion.sec.pipeline import _within_backfill
from app.ingestion.sec.xbrl import parse_companyfacts
from app.providers.mocks._fixtures import fixture_gzip_bytes
from app.providers.sec.base import FilingRef
from app.providers.sec.mock import MockSecSource


def test_parse_8k_items_from_fixture() -> None:
    items = parse_8k_items(fixture_gzip_bytes("aapl", "8k.htm.gz"))
    assert "2.02" in items and "9.01" in items  # AAPL earnings 8-K


def test_parse_companyfacts_produces_numeric_rows() -> None:
    facts = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {
                                "val": 100,
                                "end": "2025-12-31",
                                "start": "2025-01-01",
                                "accn": "a1",
                                "filed": "2026-01-15",
                                "form": "10-K",
                                "decimals": -6,
                            },
                            {
                                "val": "not-a-number",
                                "end": "2025-12-31",
                                "accn": "a1",
                                "filed": "2026-01-15",
                            },
                        ]
                    }
                }
            }
        }
    }
    rows, skipped = parse_companyfacts(company_id=1, companyfacts=facts)
    assert len(rows) == 1 and skipped == 1
    row = rows[0]
    assert row["concept_tag"] == "us-gaap:Revenues"
    assert row["period_type"] == "duration"
    assert str(row["value"]) == "100"
    assert row["accession_number"] == "a1"


def test_within_backfill_window() -> None:
    settings = Settings()
    today = date(2026, 9, 30)
    recent_10k = FilingRef(
        cik="1",
        form="10-K",
        accession_number="x",
        primary_document="d",
        filing_date="2026-02-25",
        report_date="2026-01-25",
        primary_doc_url="u",
    )
    old_10k = FilingRef(
        cik="1",
        form="10-K",
        accession_number="y",
        primary_document="d",
        filing_date="2015-02-25",
        report_date="2015-01-25",
        primary_doc_url="u",
    )
    assert _within_backfill(recent_10k, settings, today) is True
    assert _within_backfill(old_10k, settings, today) is False


def test_mock_source_lists_three_filings_and_facts() -> None:
    source = MockSecSource()
    filings = source.list_filings("0001045810")
    assert {f.form for f in filings} == {"10-K", "10-Q", "8-K"}
    facts = source.companyfacts("0001045810")
    assert "facts" in facts and "us-gaap" in facts["facts"]
