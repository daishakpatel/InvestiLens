"""Schema validation tests (spec §17.2, §13.3, DR-040). Offline."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas.research import ResearchClaim
from app.schemas.sources import DerivedMetricSource, MetricResult, SourceRecord, TextChunkSource


def test_claim_requires_at_least_one_source() -> None:
    """CIT-004: a claim with no source_ids is invalid."""
    with pytest.raises(ValidationError):
        ResearchClaim(claim_id="c1", text="Revenue grew.", source_ids=[])


def test_claim_accepts_backend_fields_optional() -> None:
    claim = ResearchClaim(claim_id="c1", text="Revenue grew.", source_ids=["s1"])
    assert claim.confidence_label is None  # backend sets this, not the LLM
    assert claim.internal_confidence is None


def test_source_record_discriminates_on_type() -> None:
    """CIT-002: SourceRecord parses to the correct variant by source_type."""
    adapter: TypeAdapter[SourceRecord] = TypeAdapter(SourceRecord)
    text = adapter.validate_python(
        {"source_type": "text_chunk", "source_id": "s1", "tier": 1, "document_id": "d1"}
    )
    assert isinstance(text, TextChunkSource)
    derived = adapter.validate_python(
        {
            "source_type": "derived_metric",
            "source_id": "m1",
            "tier": 1,
            "formula_id": "revenue_yoy",
            "formula_version": "v1",
        }
    )
    assert isinstance(derived, DerivedMetricSource)


def test_metric_result_allows_none_value_with_warning() -> None:
    """DR-041: an uncomputable metric returns None + a reason code."""
    result = MetricResult(
        value=None, unit="ratio", formula_id="current_ratio", warnings=["NOT_APPLICABLE_SECTOR"]
    )
    assert result.value is None
    assert "NOT_APPLICABLE_SECTOR" in result.warnings


def test_metric_result_preserves_decimal() -> None:
    result = MetricResult(value=Decimal("0.12340000"), unit="ratio", formula_id="gross_margin")
    assert result.value == Decimal("0.12340000")
