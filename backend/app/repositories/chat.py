"""chat_sessions + chat_messages persistence (Phase 3c, §10.14).

A session belongs to a user and a company (ADR-0006: chat requires an account). Messages store the
answer's cited source IDs, the tool trace, cost/latency, and per-message feedback for the Phase 5b
golden-set loop.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ChatMessage, ChatSession


def create_session(session: Session, *, user_id: int, company_id: int) -> ChatSession:
    row = ChatSession(user_id=user_id, company_id=company_id)
    session.add(row)
    session.flush()
    return row


def get_session(session: Session, session_id: int) -> ChatSession | None:
    return session.get(ChatSession, session_id)


def recent_messages(session: Session, *, session_id: int, limit: int) -> list[ChatMessage]:
    """The last `limit` messages for a session, oldest first (bounded memory window)."""
    rows = list(
        session.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.id.desc())
            .limit(limit)
        )
    )
    return list(reversed(rows))


def add_message(
    session: Session,
    *,
    session_id: int,
    role: str,
    content: str,
    source_ids: list[str] | None = None,
    tool_trace: dict[str, Any] | None = None,
    cost_usd: Decimal | None = None,
    latency_ms: int | None = None,
) -> ChatMessage:
    row = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
        source_ids=source_ids,
        tool_trace=tool_trace,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
    )
    session.add(row)
    session.flush()
    return row


def set_feedback(
    session: Session, *, message_id: int, rating: str, reason: str | None
) -> ChatMessage | None:
    row = session.get(ChatMessage, message_id)
    if row is None:
        return None
    row.feedback = rating
    row.feedback_reason = reason
    return row
