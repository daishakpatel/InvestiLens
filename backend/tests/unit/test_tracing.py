"""OpenTelemetry span instrumentation (OBS-001, ADR-0021). Offline: an in-memory exporter stands
in for a real collector, so these assert on actual span attributes with no infra running.
"""

from __future__ import annotations

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.citation.evidence import EvidenceItem
from app.citation.pipeline import verify_text
from app.observability.tracing import configure_tracing, span
from app.schemas.sources import TextChunkSource


def _text_ev(sid: str, text: str) -> EvidenceItem:
    return EvidenceItem(
        source=TextChunkSource(source_id=sid, tier=1, document_id="doc1", text=text),
        text=text,
        retrieval_score=0.8,
    )


def test_citation_validator_span_carries_claim_count() -> None:
    exporter = InMemorySpanExporter()
    configure_tracing(exporter=exporter)
    exporter.clear()

    ev = {"a": _text_ev("a", "Revenue was $60,922 million for fiscal 2025.")}
    verify_text("Revenue reached $60,922 million [SOURCE:a].", ev)

    spans = exporter.get_finished_spans()
    names = [s.name for s in spans]
    assert "citation.verify" in names
    verify_span = next(s for s in spans if s.name == "citation.verify")
    assert verify_span.attributes is not None
    assert verify_span.attributes["claims"] == 1


def test_span_ends_even_on_exception() -> None:
    """A span must still close (and be exported) if the wrapped call raises."""
    exporter = InMemorySpanExporter()
    configure_tracing(exporter=exporter)
    exporter.clear()

    with pytest.raises(ValueError), span("test.failing", tracer_name=__name__):
        raise ValueError("boom")

    spans = exporter.get_finished_spans()
    assert any(s.name == "test.failing" for s in spans)
