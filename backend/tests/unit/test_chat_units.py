"""Offline chat helper unit tests (Phase 3c): follow-up detection, suggestions, SSE framing."""

from __future__ import annotations

import pytest

from app.chat.service import ChatTurn, _is_followup
from app.chat.streaming import sse_events
from app.chat.suggestions import suggest
from app.rag.types import Intent
from app.schemas.chat import Citation


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("and last quarter?", True),
        ("What about margins?", True),
        ("and FY2024?", True),
        ("What were NVIDIA's gross margins across the last three fiscal years?", False),
    ],
)
def test_is_followup(question: str, expected: bool) -> None:
    assert _is_followup(question) is expected


def test_suggestions_bias_by_intent() -> None:
    out = suggest("NVDA", Intent.RISK_ANALYSIS, limit=3)
    assert len(out) == 3
    assert any("risk" in q.lower() for q in out)


async def _collect(turn: ChatTurn) -> list[bytes]:
    return [frame async for frame in sse_events(turn)]


def test_sse_frames_order() -> None:
    import asyncio

    turn = ChatTurn(
        answer="Revenue grew.[1]",
        citations=[Citation(source_id="s", number=1)],
        session_id=1,
        message_id=2,
    )
    frames = b"".join(asyncio.run(_collect(turn))).decode()
    assert "event: token" in frames
    assert (
        frames.index("event: token")
        < frames.index("event: citations")
        < frames.index("event: done")
    )
