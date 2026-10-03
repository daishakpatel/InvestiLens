"""Offline unit tests for the Phase 4a API support layer (API-002/008, ADR-0016)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.api._support import freshness_from_row, metric_to_result
from app.api.errors import ProblemException
from app.api.pagination import clamp_limit, decode_cursor, encode_cursor
from app.models import DataFreshness, FinancialMetric


def test_cursor_round_trips() -> None:
    assert decode_cursor(encode_cursor(42)) == 42
    assert decode_cursor(None) is None
    assert decode_cursor("") is None


def test_malformed_cursor_raises_422() -> None:
    with pytest.raises(ProblemException) as exc:
        decode_cursor("@@not-base64@@")
    assert exc.value.status_code == 422


def test_clamp_limit_bounds() -> None:
    assert clamp_limit(None) == 50  # default (api_default_page_size)
    assert clamp_limit(-5) == 1  # floor
    assert clamp_limit(10_000) == 200  # api_max_page_size cap


def test_freshness_defaults_to_stale_when_absent() -> None:
    fresh = freshness_from_row(None, source="sec")
    assert fresh.source == "sec" and fresh.freshness_status == "stale"


def test_freshness_maps_row_status() -> None:
    now = datetime.now(UTC)
    row = DataFreshness(
        company_id=1, source="price", status="failed", last_success_at=None, last_attempt_at=now
    )
    assert freshness_from_row(row, source="price").freshness_status == "failed"


def test_metric_to_result_surfaces_lineage_and_null_reason() -> None:
    derived = FinancialMetric(
        company_id=1,
        period="FY2025",
        period_type="FY",
        metric_name="gross_margin",
        metric_value=Decimal("0.71"),
        unit="ratio",
        is_derived=True,
        formula_id="gross_margin",
        quality_flags={
            "formula_version": "v1",
            "inputs": [{"name": "revenue", "value": "100", "source_id": "xbrl:1"}],
            "warnings": [],
        },
    )
    result = metric_to_result(derived)
    assert result.formula_version == "v1" and result.inputs[0].name == "revenue"

    na = FinancialMetric(
        company_id=1,
        period="FY2025",
        period_type="FY",
        metric_name="gross_margin",
        metric_value=None,
        unit="ratio",
        quality_flags={"warnings": ["NOT_APPLICABLE_SECTOR"]},
    )
    out = metric_to_result(na)
    assert out.value is None and out.warnings == ["NOT_APPLICABLE_SECTOR"]
