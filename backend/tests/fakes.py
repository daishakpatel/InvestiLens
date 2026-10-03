"""Deterministic fake LLM for Phase 3b tests (no key/network; ADR-0009 live path needs a key).

It reads the evidence source IDs out of the generation prompt and returns section-shaped JSON that
cites a real id with text overlapping the evidence (so it passes Phase 3a verification). Sections
named in `broken` return an invalid shape both times, to exercise per-section failure isolation.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from app.providers.base import LLMClient, LLMMessage

_ID = re.compile(r"source_id=([^\]]+)\]")


def _label(system: str) -> str:
    s = system.lower()
    if "risk" in s and "extract" in s:
        return "risks"
    if "upside" in s:
        return "bull"
    if "downside" in s:
        return "bear"
    if "news" in s and "two sentences" in s:
        return "news"
    if "management statements" in s or "group management" in s:
        return "mgmt"
    return "claims"


class FakeLLM(LLMClient):
    def __init__(self, *, broken: set[str] | None = None) -> None:
        self._broken = broken or set()

    async def complete(self, messages: Sequence[LLMMessage], *, model: str, max_tokens: int) -> str:
        # Chat synthesis: cite the first evidence id with text overlapping it (passes Phase 3a).
        user = messages[-1].content
        ids = _ID.findall(user)
        if not ids:
            return "I could not find supporting evidence."
        sid = ids[0]
        return f"The company reported that {_snippet(user, sid)} [SOURCE:{sid}]."

    async def complete_json(
        self, messages: Sequence[LLMMessage], *, model: str, schema: dict[str, Any], max_tokens: int
    ) -> dict[str, Any]:
        system = messages[0].content
        user = messages[-1].content
        label = _label(system)
        ids = _ID.findall(user)
        if label in self._broken or not ids:
            return {}  # invalid shape → repair also fails → section marked insufficient
        sid = ids[0]
        # Text overlapping the evidence so lexical entailment supports it; no invented numbers.
        snippet = _snippet(user, sid)
        text = f"The company discussed {snippet}".strip()
        if label == "risks":
            return {
                "risks": [{"category": "supply_chain", "description": text, "source_ids": [sid]}]
            }
        if label in ("bull", "bear"):
            title = "Potential upside" if label == "bull" else "Potential downside"
            return {
                "factors": [
                    {
                        "title": title,
                        "claims": [{"text": text, "source_ids": [sid]}],
                        "monitoring_indicator": "revenue",
                    }
                ]
            }
        if label == "news":
            return {
                "summaries": [
                    {"news_id": sid, "category": "general", "summary": text, "source_ids": [sid]}
                ]
            }
        if label == "mgmt":
            return {
                "statements": [
                    {
                        "topic": "revenue_outlook",
                        "period": "FY2025",
                        "text": text,
                        "source_ids": [sid],
                    }
                ]
            }
        return {"claims": [{"text": text, "source_ids": [sid]}]}


def _snippet(user: str, sid: str) -> str:
    """Return a few words of the evidence block for `sid`, for a verifiable claim."""
    marker = f"source_id={sid}]"
    start = user.find(marker)
    tail = user[start + len(marker) :] if start >= 0 else user
    words = re.findall(r"[A-Za-z]+", tail)
    return " ".join(words[:8])
