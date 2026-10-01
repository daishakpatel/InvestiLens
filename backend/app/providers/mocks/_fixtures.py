"""Locate and load the frozen fixture dataset (Phase 0d).

The mock providers read these files instead of calling SEC / price / news APIs, so development
and CI run fully offline (DR-004). `.gz` files are decompressed transparently.
"""

from __future__ import annotations

import csv
import gzip
import json
from functools import lru_cache
from io import StringIO
from pathlib import Path
from typing import Any

# app/providers/mocks/_fixtures.py -> backend/tests/fixtures
FIXTURES_DIR = Path(__file__).resolve().parents[3] / "tests" / "fixtures"


def fixture_path(*parts: str) -> Path:
    return FIXTURES_DIR.joinpath(*parts)


def load_json(*parts: str) -> Any:
    path = fixture_path(*parts)
    if path.suffix == ".gz":
        with gzip.open(path) as fh:
            return json.loads(fh.read())
    return json.loads(path.read_text())


def load_csv_rows(*parts: str) -> list[dict[str, str]]:
    text = fixture_path(*parts).read_text()
    return list(csv.DictReader(StringIO(text)))


@lru_cache
def company_reference() -> dict[str, dict[str, str]]:
    """Map ticker -> company reference row from companies.json."""
    data = load_json("companies.json")["companies"]
    return {row["ticker"]: row for row in data}


def fixture_gzip_bytes(*parts: str) -> bytes:
    """Return decompressed bytes of a `.gz` fixture (e.g. a frozen filing HTML)."""
    with gzip.open(fixture_path(*parts)) as fh:
        data: bytes = fh.read()
    return data
