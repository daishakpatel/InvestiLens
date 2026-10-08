"""Eval runner + gate + A/B + feedback integration tests (Phase 5b, spec §18).

Real Postgres + pgvector; skips offline. Seeds a small TST corpus, drives the eval harness end to
end with the deterministic FakeLLM + FakeJudge, and proves: metrics compute + persist, the CI gate
catches a deliberate citation-accuracy regression (DoD #4), the A/B harness diffs two configs, and
chat feedback is triaged into golden candidates.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

import app.repositories.eval_runs as eval_repo
from app.config import get_settings
from app.embeddings.pipeline import embed_pending
from app.eval.ab import run_ab
from app.eval.dataset import load_golden
from app.eval.feedback import collect_flagged
from app.eval.gate import check_gate
from app.eval.judge import FakeJudge
from app.eval.runner import persist_run, run_eval
from app.models import (
    ChatMessage,
    ChatSession,
    Company,
    Document,
    DocumentChunk,
    EvalResult,
    FinancialMetric,
    FiscalCalendar,
    User,
)
from app.providers.mocks.embeddings import MockEmbeddingClient
from tests.fakes import FakeLLM

_SMOKE = Path(__file__).resolve().parents[1] / "eval" / "smoke.jsonl"
_CHUNKS = [
    "Revenue grew on strong data center demand across all regions in fiscal 2025.",
    "Supply chain risk: reliance on a few foundry partners raised disruption exposure.",
]
_REV = {2023: "26974000000", 2024: "60922000000", 2025: "130497000000"}


@pytest.fixture(scope="module")
def _migrated(test_db_url: str) -> None:
    from tests.integration.conftest import _MIGRATIONS_DIR

    cfg = Config()
    cfg.set_main_option("script_location", _MIGRATIONS_DIR)
    cfg.set_main_option("sqlalchemy.url", test_db_url)
    command.upgrade(cfg, "head")


@pytest.fixture
def session(_migrated: None, test_engine: Engine) -> Iterator[Session]:
    with Session(test_engine) as s:
        yield s
        s.rollback()


@pytest.fixture
def seed(session: Session) -> int:
    user = User(email="e@example.com", password_hash="x")  # noqa: S106  # test fixture
    company = Company(ticker="TST", cik="0000000011", name="Test Corp")
    session.add_all([user, company])
    session.flush()
    doc = Document(company_id=company.id, document_type="filing", source_tier=1, content_hash="d1")
    session.add(doc)
    session.flush()
    for i, body in enumerate(_CHUNKS):
        session.add(
            DocumentChunk(
                document_id=doc.id,
                company_id=company.id,
                chunk_index=i,
                chunk_type="text",
                text=body,
                section="Item 1A",
                section_path=["Item 1A"],
                paragraph_id=f"{doc.id}_{i}",
                char_start=0,
                char_end=len(body),
                tier=1,
                filing_type="10-K",
                parser_version="doc-parse-v1",
            )
        )
    for fy, value in _REV.items():
        session.add(
            FinancialMetric(
                company_id=company.id,
                period=f"FY{fy}",
                fiscal_year=fy,
                period_type="FY",
                metric_name="revenue",
                metric_value=Decimal(value),
                unit="USD",
                source_id=f"xbrl:TST:revenue:FY{fy}",
                is_latest=True,
            )
        )
        session.add(
            FiscalCalendar(
                company_id=company.id,
                fiscal_year=fy,
                fiscal_quarter=None,
                period_start=date(fy - 1, 2, 1),
                period_end=date(fy, 1, 31),
                period_type="FY",
            )
        )
    session.flush()
    embed_pending(session, client=MockEmbeddingClient())
    return user.id


def _run(session: Session, user_id: int):  # type: ignore[no-untyped-def]
    questions = load_golden(_SMOKE)
    return questions, run_eval(
        session,
        questions,
        user_id=user_id,
        llm=FakeLLM(),
        judge=FakeJudge(),
        settings=get_settings(),
    )


# --- metrics compute + persist (DoD #2, §18.5) ----------------------------------------
def test_smoke_eval_computes_and_persists(session: Session, seed: int) -> None:
    questions, summary = _run(session, seed)
    assert summary.n == len(questions) == 6

    m = summary.metrics
    # The metric question is answered with the right number; the abstain cases all abstain.
    assert m["numeric_accuracy"] == 1.0
    assert m["abstention_accuracy"] == 1.0  # advice / forward-looking / injection / unknown co.
    assert m["hallucination_rate"] == 0.0  # nothing answered that should have abstained
    assert m["citation_accuracy"] is not None  # computed over answered factual questions

    run_id = persist_run(session, summary, name="smoke-test", config_hash="cfg", git_sha="abc1234")
    stored = eval_repo.list_runs(session, limit=5, after_id=None)
    assert any(r.id == run_id and (r.metrics or {})["n"] == 6 for r in stored)
    rows = session.scalars(select(EvalResult).where(EvalResult.run_id == run_id)).all()
    assert len(rows) == 6 and all(r.metrics is not None for r in rows)


# --- CI gate catches a deliberate regression (DoD #4, EVAL-002) -----------------------
def test_gate_blocks_citation_accuracy_regression(session: Session, seed: int) -> None:
    _questions, summary = _run(session, seed)
    baseline = dict(summary.metrics)
    assert check_gate(summary.metrics, baseline).passed  # a run never regresses against itself

    # Deliberately break it: drop citation accuracy well past the 1-point threshold.
    broken = dict(summary.metrics)
    broken["citation_accuracy"] = (baseline["citation_accuracy"] or 1.0) - 0.2
    result = check_gate(broken, baseline)
    assert not result.passed and any("citation_accuracy" in f for f in result.failures)


# --- A/B harness produces a per-question diff (DoD #5, §18.7) --------------------------
def test_ab_harness_diffs_two_configs(session: Session, seed: int) -> None:
    questions = load_golden(_SMOKE)
    base = get_settings()
    variant = base.model_copy(update={"rag_rerank_enabled": not base.rag_rerank_enabled})
    result = run_ab(
        session,
        questions,
        user_id=seed,
        llm=FakeLLM(),
        judge=FakeJudge(),
        config_a=base,
        config_b=variant,
    )
    assert result.a.n == result.b.n == 6
    assert "abstention_accuracy" in result.metric_deltas  # shared aggregate metric diffed
    assert isinstance(result.question_diffs, list)  # per-question diff structure present


# --- feedback → golden triage (DoD / scope #9, §18.9) ---------------------------------
def test_feedback_triage_promotes_flagged_questions(session: Session, seed: int) -> None:
    company = session.scalars(select(Company).where(Company.ticker == "TST")).one()
    chat = ChatSession(user_id=seed, company_id=company.id)
    session.add(chat)
    session.flush()
    session.add(ChatMessage(session_id=chat.id, role="user", content="What is TST's debt?"))
    session.flush()
    session.add(
        ChatMessage(
            session_id=chat.id,
            role="assistant",
            content="I couldn't find evidence.",
            feedback="down",
            feedback_reason="should have found it",
        )
    )
    session.flush()

    flagged = collect_flagged(session)
    assert len(flagged) == 1
    assert flagged[0].question == "What is TST's debt?"
    assert flagged[0].company == "TST"
    assert flagged[0].reason == "should have found it"
    assert flagged[0].expected_answer == ""  # human fills this before promotion
