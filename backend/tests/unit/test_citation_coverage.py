"""Citation edge-branch coverage (Phase 5a, DoD: 100% on `app/citation`). Offline.

`test_citation.py` covers the main verification/rendering behavior; this file closes the
remaining defensive branches so the `citation/` coverage gate can be enforced at 100%. Each test
targets a real behavior (empty evidence, date citations, unparseable numbers, non-int source ids,
every reference-label variant, the reject partial-policy), not a line for its own sake.
"""

from __future__ import annotations

from decimal import Decimal

from app.citation import extract, resolver, verify
from app.citation.confidence import score_claim
from app.citation.entailment import Entailer, get_entailer
from app.citation.evidence import EvidenceItem
from app.citation.extract import NumberToken, split_claims
from app.citation.pipeline import verify_text
from app.citation.render import citation_text
from app.config import get_settings
from app.schemas.citations import EntailmentLabel
from app.schemas.sources import (
    DerivedMetricSource,
    EarningsReleaseSource,
    NewsItemSource,
    TableChunkSource,
    TextChunkSource,
    _SourceBase,
)


def _text_ev(sid: str, text: str) -> EvidenceItem:
    return EvidenceItem(
        source=TextChunkSource(source_id=sid, tier=1, document_id="d1", text=text),
        text=text,
        retrieval_score=0.8,
    )


# --- confidence: no cited evidence → limited (confidence.py) --------------------------


def test_score_claim_with_no_evidence_is_limited() -> None:
    score, label = score_claim([], "unsupported")
    assert score == 0.0 and label == "limited_evidence"


# --- entailment: a claim with no scoreable terms is unsupported (entailment.py) -------


def test_entailer_empty_claim_is_unsupported() -> None:
    entailer = get_entailer(get_settings())
    assert entailer.check("", "Revenue grew strongly.") == "unsupported"


# --- evidence: a table source's labels feed searchable_text (evidence.py) -------------


def test_table_source_searchable_text_includes_labels() -> None:
    table = TableChunkSource(
        source_id="t1",
        tier=1,
        document_id="d1",
        table_id="tbl0",
        row_labels=["Revenue"],
        col_labels=["FY2025"],
        cell_refs=["60922"],
    )
    text = EvidenceItem(source=table, text="").searchable_text()
    assert "Revenue" in text and "FY2025" in text and "60922" in text


# --- extract: unparseable decimals and empty input (extract.py) -----------------------


def test_to_decimal_rejects_malformed_number() -> None:
    assert extract._to_decimal("1.2.3") is None  # InvalidOperation → None, never raises


def test_split_claims_of_empty_text_is_empty() -> None:
    assert split_claims("   ") == []


# --- render: every reference-label variant (render.py) --------------------------------


def test_citation_text_for_table_source() -> None:
    src = TableChunkSource(source_id="t1", tier=1, document_id="d1", table_id="tbl0")
    assert citation_text(src) == "d1 — table tbl0"


def test_citation_text_for_earnings_and_news() -> None:
    earnings = EarningsReleaseSource(
        source_id="e1", tier=2, source_type="earnings_release", document_id="d9"
    )
    assert "earnings release" in citation_text(earnings)
    news = NewsItemSource(source_id="n1", tier=4, news_id="42", publisher="Reuters")
    assert citation_text(news) == "Reuters — 42"


def test_citation_text_falls_back_to_source_id() -> None:
    # Defensive fallback for a source with no recognized anchor fields.
    base = _SourceBase(source_id="unknown-123", tier=5)
    assert citation_text(base) == "unknown-123"  # type: ignore[arg-type]


# --- resolver: a non-integer id degrades to a sentinel, never raises (resolver.py) ----


def test_as_int_sentinel_on_non_integer() -> None:
    assert resolver._as_int("not-an-int") == -1
    assert resolver._as_int("17") == 17


# --- verify: _number_supported branches (verify.py) -----------------------------------


def test_number_supported_date_token_matches_source_text() -> None:
    ev = [_text_ev("a", "The filing was dated 2025-01-31 for fiscal 2025.")]
    token = NumberToken(raw="2025-01-31", value=None, kind="date")
    assert verify._number_supported(token, ev, rel_tol=0.01) is True


def test_number_supported_unparseable_value_does_not_block() -> None:
    token = NumberToken(raw="??", value=None, kind="money")
    assert verify._number_supported(token, [], rel_tol=0.01) is True


def test_number_supported_returns_false_when_no_candidate_matches() -> None:
    ev = [_text_ev("a", "Revenue was modest this year.")]
    token = NumberToken(raw="999999", value=Decimal("999999"), kind="number")
    assert verify._number_supported(token, ev, rel_tol=0.01) is False


def test_number_supported_accepts_within_relative_tolerance() -> None:
    # A near-match (not exact) that is inside the relative tolerance still counts (CIT-005 L2).
    ev = [
        EvidenceItem(
            source=DerivedMetricSource(
                source_id="d",
                tier=1,
                formula_id="x",
                formula_version="v1",
                value=Decimal("100"),
            ),
            text="",
        )
    ]
    token = NumberToken(raw="100.5", value=Decimal("100.5"), kind="number")
    assert verify._number_supported(token, ev, rel_tol=0.01) is True  # 0.5 ≤ 100.5 * 0.01


class _AlwaysPartial(Entailer):
    def check(self, claim: str, source_text: str) -> EntailmentLabel:
        return "partially"


def test_partial_entailment_rejected_under_reject_policy() -> None:
    ev = [_text_ev("a", "Revenue was $60,922 million for fiscal 2025.")]
    reject_settings = get_settings().model_copy(update={"citation_partial_policy": "reject"})
    out = verify_text(
        "Revenue was $60,922 million [SOURCE:a].",
        ev,
        settings=reject_settings,
        entailer=_AlwaysPartial(),
    )
    assert out.claims[0].status == "rejected" and out.claims[0].reason_code == "UNSUPPORTED"


def test_partial_entailment_softened_under_default_policy() -> None:
    ev = [_text_ev("a", "Revenue was $60,922 million for fiscal 2025.")]
    out = verify_text(
        "Revenue was $60,922 million [SOURCE:a].",
        ev,
        entailer=_AlwaysPartial(),
    )
    assert out.claims[0].status == "softened"
