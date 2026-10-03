"""Research section-generator + payload unit tests (Phase 3b). Offline, fake LLM.

Refs: §10, §17.2, CIT-005 (verification gates every claim), FR-020 (every claim cited).
"""

from __future__ import annotations

from app.citation.evidence import EvidenceItem
from app.research.generator import accepted_by_index, generate_section
from app.schemas.sources import TextChunkSource
from tests.fakes import FakeLLM


def _ev(sid: str, text: str, *, tier: int = 1) -> EvidenceItem:
    return EvidenceItem(
        source=TextChunkSource(source_id=sid, tier=tier, document_id="d"), text=text
    )


def test_section_generates_verified_claims() -> None:
    ev = [_ev("c1", "Revenue grew on strong data center demand during the period.")]
    gen = generate_section(FakeLLM(), section="revenue_analysis", payload={}, evidence=ev)
    assert not gen.insufficient
    accepted = accepted_by_index(gen.verified)
    assert accepted
    # Every accepted claim carries a verified citation (FR-020).
    assert all(vc.source_ids == ["c1"] for vc in accepted.values())
    assert all(vc.status in ("accepted", "softened") for vc in accepted.values())


def test_claim_citing_absent_evidence_is_dropped() -> None:
    # No evidence → fake returns {} → section insufficient, no claims leak through.
    gen = generate_section(FakeLLM(), section="revenue_analysis", payload={}, evidence=[])
    assert gen.insufficient
    assert accepted_by_index(gen.verified) == {}


def test_risk_section_shape() -> None:
    ev = [_ev("r1", "Supply chain depends on a limited number of foundry partners in Taiwan.")]
    gen = generate_section(FakeLLM(), section="risks", payload={}, evidence=ev)
    assert gen.items and gen.items[0].meta.get("category") == "supply_chain"
    assert not gen.insufficient


def test_malformed_section_is_insufficient_not_crash() -> None:
    ev = [_ev("c1", "Revenue grew on strong data center demand.")]
    gen = generate_section(
        FakeLLM(broken={"claims"}), section="revenue_analysis", payload={}, evidence=ev
    )
    assert gen.insufficient  # malformed output → empty, not an exception
    assert accepted_by_index(gen.verified) == {}


def test_factor_section_groups_claims() -> None:
    ev = [_ev("c1", "Demand for AI infrastructure remained strong across segments.")]
    gen = generate_section(FakeLLM(), section="bull_factors", payload={}, evidence=ev)
    assert gen.items and gen.items[0].meta.get("title") == "Potential upside"
    assert gen.items[0].meta.get("factor_idx") == 0
