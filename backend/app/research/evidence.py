"""Adapters that turn retrieval + metric rows into verifier evidence (Phase 3b glue).

The report generator pulls evidence from two places — Phase 2c document retrieval and Phase 1c
structured metrics — and both must become Phase 3a `EvidenceItem`s so the citation verifier can
check every claim against them. Structured metrics carry a typed derived/xbrl source so numeric
claims verify against the exact backend value (CIT-003).
"""

from __future__ import annotations

from app.citation.evidence import EvidenceItem
from app.models import FinancialMetric
from app.rag.types import Evidence as RagEvidence
from app.schemas.sources import DerivedMetricSource, XbrlFactSource


def from_rag(evidence: RagEvidence) -> EvidenceItem:
    """Phase 2c retrieved chunk → verifier evidence (carries the chunk's typed source + text)."""
    return EvidenceItem(
        source=evidence.source,
        text=evidence.text,
        retrieval_score=evidence.scores.get("rerank", evidence.scores.get("rrf", 0.5)),
    )


def metric_source_id(metric: FinancialMetric) -> str:
    """Stable citation id for a metric row (its stored source_id, else a synthesized one)."""
    return metric.source_id or f"metric:{metric.metric_name}:{metric.period}"


def from_metric(metric: FinancialMetric) -> EvidenceItem:
    """financial_metrics row → verifier evidence. Derived rows expose formula lineage (CIT-003)."""
    sid = metric_source_id(metric)
    text = f"{metric.metric_name} {metric.period} = {metric.metric_value} {metric.unit}".strip()
    if metric.is_derived:
        flags = metric.quality_flags or {}
        inputs = [dict(i) for i in flags.get("inputs", [])]
        source = DerivedMetricSource(
            source_id=sid,
            tier=1,
            formula_id=metric.formula_id or metric.metric_name,
            formula_version=str(flags.get("formula_version") or ""),
            input_source_ids=[str(i.get("source_id")) for i in inputs if i.get("source_id")],
            value=metric.metric_value,
            period=metric.period,
        )
    else:
        source = XbrlFactSource(  # type: ignore[assignment]
            source_id=sid,
            tier=1,
            accession_number=metric.as_reported_accession or sid,
            concept_tag=metric.metric_name,
            unit=metric.unit,
            value=metric.metric_value,
        )
    return EvidenceItem(source=source, text=text, retrieval_score=0.9)
