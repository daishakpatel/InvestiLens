"""Chat request/response and citation schemas (spec §24.2, §13)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.schemas.research import EvidenceLabel


class Citation(BaseModel):
    """A rendered citation shown next to an answer (CIT-006)."""

    source_id: str
    number: int
    title: str | None = None
    section_path: list[str] = []
    page: int | None = None  # PDFs only
    tier: int | None = None


class ToolTraceEntry(BaseModel):
    tool: str
    latency_ms: int | None = None


class ChatRequest(BaseModel):
    company: str
    question: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation] = []
    evidence_label: EvidenceLabel | None = None
    abstained: bool = False
    refused: bool = False  # out-of-scope / advice refusal (distinct from abstention)
    tool_trace: list[ToolTraceEntry] = []
    suggested_questions: list[str] = []
    session_id: str | None = None
    message_id: str | None = None  # for POST /chat/messages/{id}/feedback


class ChatMessage(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    citations: list[Citation] = []


class ChatSession(BaseModel):
    id: str
    company: str
    messages: list[ChatMessage] = []


class FeedbackRequest(BaseModel):
    rating: Literal["up", "down"]
    reason: str | None = None
