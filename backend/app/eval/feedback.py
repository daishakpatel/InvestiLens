"""Feedback → golden-set triage (spec §18.9, scope #9).

Turns Phase 3c thumbs-down chat feedback into candidate golden questions so the eval set grows
over time. A candidate carries the original question + company + the system's (bad) answer and the
user's reason; a human fills `expected_answer`/`must_abstain` before it is promoted — we never
auto-add an answer we can't verify (no LLM-invented ground truth).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ChatMessage, ChatSession, Company


@dataclass(frozen=True)
class FlaggedCandidate:
    company: str
    question: str
    system_answer: str
    reason: str | None
    # Filled by a human during triage before promotion:
    expected_answer: str = ""
    must_abstain: bool = False
    tags: tuple[str, ...] = ("from_feedback", "triage")


def collect_flagged(session: Session, *, limit: int = 100) -> list[FlaggedCandidate]:
    """Down-voted assistant turns, paired with the question that prompted them."""
    rows = session.execute(
        select(ChatMessage, Company.ticker)
        .join(ChatSession, ChatSession.id == ChatMessage.session_id)
        .join(Company, Company.id == ChatSession.company_id)
        .where(ChatMessage.role == "assistant", ChatMessage.feedback == "down")
        .order_by(ChatMessage.id.desc())
        .limit(limit)
    ).all()

    candidates: list[FlaggedCandidate] = []
    for msg, ticker in rows:
        question = _preceding_question(session, session_id=msg.session_id, before_id=msg.id)
        if question is None:
            continue
        candidates.append(
            FlaggedCandidate(
                company=ticker,
                question=question,
                system_answer=msg.content,
                reason=msg.feedback_reason,
            )
        )
    return candidates


def _preceding_question(session: Session, *, session_id: int, before_id: int) -> str | None:
    """The user message immediately before an assistant message in the same session."""
    return session.scalars(
        select(ChatMessage.content)
        .where(
            ChatMessage.session_id == session_id,
            ChatMessage.role == "user",
            ChatMessage.id < before_id,
        )
        .order_by(ChatMessage.id.desc())
        .limit(1)
    ).first()


def to_golden_draft(candidate: FlaggedCandidate, *, id_: str) -> str:
    """Render a candidate as a golden JSONL line (expected_answer blank until a human fills it)."""
    row = {
        "id": id_,
        "company": candidate.company,
        "question": candidate.question,
        "intent": "TRIAGE",
        "expected_answer": candidate.expected_answer,
        "expected_numeric": None,
        "expected_sources": [],
        "must_abstain": candidate.must_abstain,
        "tags": list(candidate.tags),
        "_triage": {"system_answer": candidate.system_answer, "reason": candidate.reason},
    }
    return json.dumps(row)


def candidate_dict(candidate: FlaggedCandidate) -> dict[str, object]:
    return asdict(candidate)
