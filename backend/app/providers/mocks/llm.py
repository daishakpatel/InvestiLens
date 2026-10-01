"""Mock LLMClient: replays recorded responses, else returns a deterministic stub (Phase 0d).

Integration tests replay recorded fixtures instead of calling a live model (§30.2). A recording
is keyed by a stable hash of (model + messages). Real recordings are added in Phase 3 once an
LLM key exists (ADR-0009); until then a deterministic stub keeps offline tests reproducible.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Any

from app.providers.base import LLMClient, LLMMessage
from app.providers.mocks._fixtures import fixture_path

_RECORDINGS = fixture_path("llm_recordings")


def _key(messages: Sequence[LLMMessage], model: str) -> str:
    payload = {
        "model": model,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return digest[:16]


def _load_recording(key: str) -> dict[str, Any] | None:
    path = _RECORDINGS / f"{key}.json"
    if path.exists():
        recording: dict[str, Any] = json.loads(path.read_text())
        return recording
    return None


class MockLLMClient(LLMClient):
    async def complete(self, messages: Sequence[LLMMessage], *, model: str, max_tokens: int) -> str:
        recording = _load_recording(_key(messages, model))
        if recording and recording.get("kind") == "text":
            return str(recording["response"])
        # Deterministic stub: echo a short digest so tests are stable and offline.
        return f"MOCK_COMPLETION[{_key(messages, model)}]"

    async def complete_json(
        self,
        messages: Sequence[LLMMessage],
        *,
        model: str,
        schema: dict[str, Any],
        max_tokens: int,
    ) -> dict[str, Any]:
        recording = _load_recording(_key(messages, model))
        if recording and recording.get("kind") == "json":
            result: dict[str, Any] = recording["response"]
            return result
        return {"_mock": True, "_key": _key(messages, model)}
