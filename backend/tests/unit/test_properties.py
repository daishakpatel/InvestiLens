"""Property-based invariants for retrieval and chunking (Phase 5a, scope #1). Offline.

Complements the formula invariants in `test_metrics.py`. Covers two invariants the spec calls
out explicitly: RRF fusion ordering is stable/deterministic (RAG-011), and no chunk ever crosses
a section boundary (CH-001). Uses Hypothesis so the invariants hold across many shapes, not just
the hand-picked fixtures.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.ingestion.documents.blocks import Block
from app.ingestion.documents.chunker import FilingMeta, chunk_filing
from app.rag.fusion import reciprocal_rank_fusion

# --- RRF fusion ordering stability (RAG-011) ------------------------------------------

# Small id pools keep the lists meaningfully overlapping (so fusion actually combines ranks).
_ids = st.lists(st.integers(min_value=1, max_value=12), unique=True, max_size=12)
_ranked_lists = st.lists(_ids, min_size=1, max_size=4)


@given(_ranked_lists)
def test_rrf_is_deterministic(lists: list[list[int]]) -> None:
    """Same input → identical fused output (ids, scores, and order)."""
    assert reciprocal_rank_fusion(lists) == reciprocal_rank_fusion(lists)


@given(_ranked_lists)
def test_rrf_is_commutative_over_lists(lists: list[list[int]]) -> None:
    """RRF sums per-list contributions, so the order the lists are fused in is irrelevant.

    Scores are compared with a tolerance because float summation order differs.
    """
    forward = dict(reciprocal_rank_fusion(lists))
    backward = dict(reciprocal_rank_fusion(list(reversed(lists))))
    assert forward.keys() == backward.keys()
    assert all(forward[i] == pytest.approx(backward[i]) for i in forward)


@given(_ranked_lists)
def test_rrf_output_is_sorted_descending(lists: list[list[int]]) -> None:
    fused = reciprocal_rank_fusion(lists)
    scores = [score for _id, score in fused]
    assert scores == sorted(scores, reverse=True)
    # Every distinct input id appears exactly once in the fused result (no drops, no dupes).
    assert {i for lst in lists for i in lst} == {i for i, _ in fused}


@given(_ids.filter(lambda xs: len(xs) >= 2))
def test_rrf_rank_dominance(ids: list[int]) -> None:
    """A doc ranked strictly higher in every list outscores one ranked strictly lower."""
    # One list, so fused order must equal input order (best-first).
    fused = reciprocal_rank_fusion([ids])
    assert [i for i, _ in fused] == ids


# --- No chunk crosses a section boundary (CH-001) -------------------------------------

_CORE_ITEMS = ["1", "1A", "2", "3", "5", "7"]  # detectable 10-K item codes


def _tagged_blocks(para_counts: list[int]) -> tuple[list[Block], FilingMeta]:
    """Build a synthetic filing where every body paragraph carries its section's sigil.

    `§CODE§` tags let the test detect whether any emitted chunk mixes two sections' text.
    """
    blocks: list[Block] = []
    for code, n_paras in zip(_CORE_ITEMS, para_counts, strict=True):
        blocks.append(Block(kind="text", text=f"Item {code}. Section heading {code}"))
        for j in range(n_paras):
            # Long enough that several paragraphs can force a flush within one section.
            blocks.append(Block(kind="text", text=f"§{code}§ body paragraph {j}. " + "lorem " * 40))
    meta = FilingMeta(
        document_id=7,
        company_id=1,
        company_name="Test Co",
        filing_type="10-K",
        period_label="FY2025",
    )
    return blocks, meta


@settings(max_examples=50)
@given(st.lists(st.integers(min_value=0, max_value=6), min_size=6, max_size=6))
def test_no_chunk_crosses_a_section_boundary(para_counts: list[int]) -> None:
    blocks, meta = _tagged_blocks(para_counts)
    rows = chunk_filing(blocks, meta)
    for row in rows:
        sigils = {tok for tok in row["text"].split() if tok.startswith("§")}
        # A chunk may contain many paragraphs, but all from ONE section (CH-001).
        assert len(sigils) <= 1, f"chunk mixes sections: {sigils}"
        if sigils:
            code = next(iter(sigils)).strip("§")
            assert row["parent_section_id"] == f"{meta.document_id}_{code}"
            assert row["section_path"] == [f"Item {code}"]
