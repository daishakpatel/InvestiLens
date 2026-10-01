"""Chat Q&A endpoints (spec §24.2, §13). Streaming via SSE (API-004)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse

from app.schemas.chat import ChatRequest, ChatResponse, ChatSession, FeedbackRequest

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> ChatResponse:
    return ChatResponse(
        answer="Example answer.",
        citations=[],
        evidence_label="supported",
        abstained=False,
        tool_trace=[],
        session_id=body.session_id,
    )


@router.post("/stream")
async def chat_stream(body: ChatRequest) -> StreamingResponse:
    """SSE token stream (API-004). Stub emits one token then closes."""

    async def _stream() -> AsyncIterator[bytes]:
        yield b'event: token\ndata: {"text": "Example"}\n\n'

    return StreamingResponse(_stream(), media_type="text/event-stream")


@router.get("/sessions/{session_id}", response_model=ChatSession)
async def get_session(session_id: str) -> ChatSession:
    return ChatSession(id=session_id, company="NVDA", messages=[])


@router.post("/messages/{message_id}/feedback", status_code=204)
async def message_feedback(message_id: str, body: FeedbackRequest) -> None:
    return None
