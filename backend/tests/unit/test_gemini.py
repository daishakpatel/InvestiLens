"""Gemini LLM client unit tests (ADR-0032). Offline — MockTransport, no key, no network.

Refs: SEC-001 (key in a header, never the URL), SEC-015 (host allowlist), NFR-015 (every call
logged), DR-004 (mock stays the default), RAG-050 (model routing by configured tier).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest

from app.config import get_settings
from app.providers import get_llm_client
from app.providers.base import LLMMessage
from app.providers.gemini import THINKING_ALLOWANCE_TOKENS, GeminiLLMClient
from app.providers.mocks.llm import MockLLMClient
from app.utils.http import HardenedHttpClient

_MESSAGES = [
    LLMMessage("system", "Cite sources."),
    LLMMessage("user", "What changed?"),
    LLMMessage("assistant", "Revenue rose."),
    LLMMessage("user", "Why?"),
]


def _client(response: dict[str, Any], seen: list[httpx.Request]) -> GeminiLLMClient:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=json.dumps(response).encode())

    inner = httpx.Client(
        transport=httpx.MockTransport(handler), headers={"x-goog-api-key": "test-key"}
    )
    http = HardenedHttpClient(
        user_agent="t",
        allowed_hosts=frozenset({"generativelanguage.googleapis.com"}),
        rate_per_sec=1000,
        client=inner,
    )
    return GeminiLLMClient(client=http)


def _answer(*parts: dict[str, Any], finish: str = "STOP") -> dict[str, Any]:
    return {
        "candidates": [{"content": {"parts": list(parts)}, "finishReason": finish}],
        "usageMetadata": {
            "promptTokenCount": 9,
            "candidatesTokenCount": 3,
            "thoughtsTokenCount": 5,
        },
    }


def test_complete_builds_the_request_and_skips_thoughts() -> None:  # SEC-001, RAG-050
    seen: list[httpx.Request] = []
    client = _client(_answer({"text": "hidden", "thought": True}, {"text": "Demand grew."}), seen)
    answer = asyncio.run(client.complete(_MESSAGES, model="gemini-3.8-flash", max_tokens=20))
    assert answer == "Demand grew."  # the model's reasoning is never returned as the answer

    request = seen[0]
    assert request.url.path.endswith("/models/gemini-3.8-flash:generateContent")
    assert request.headers["x-goog-api-key"] == "test-key"
    assert "key" not in request.url.params  # SEC-001: the key never travels in the URL
    body = json.loads(request.content)
    assert body["systemInstruction"] == {"parts": [{"text": "Cite sources."}]}
    assert [c["role"] for c in body["contents"]] == ["user", "model", "user"]
    # Thinking shares the output cap, so a 20-token cap alone would leave no room for an answer.
    assert body["generationConfig"]["maxOutputTokens"] == 20 + THINKING_ALLOWANCE_TOKENS
    assert "responseMimeType" not in body["generationConfig"]


def test_complete_rewrites_grouped_citations_to_one_marker_each() -> None:  # CIT-001
    # The verifier reads one [SOURCE:id] per source; an answer cited any other way is discarded.
    raw = (
        "Few foundries [cite: 51_1A_4, 40_1A_4]. Costs [SOURCE:a_1, SOURCE:news:7]. "
        "Growth [source_id=52_7_207]. Fine [SOURCE:x]."
    )
    client = _client(_answer({"text": raw}), [])
    answer = asyncio.run(client.complete(_MESSAGES, model="m", max_tokens=20))
    assert answer == (
        "Few foundries [SOURCE:51_1A_4][SOURCE:40_1A_4]. Costs [SOURCE:a_1][SOURCE:news:7]. "
        "Growth [SOURCE:52_7_207]. Fine [SOURCE:x]."
    )


def test_complete_json_uses_json_mode_and_returns_an_object() -> None:  # RAG-050
    seen: list[httpx.Request] = []
    client = _client(_answer({"text": '{"same_passage": true}'}), seen)
    result = asyncio.run(
        client.complete_json(_MESSAGES, model="gemini-3.5-flash-lite", schema={}, max_tokens=20)
    )
    assert result == {"same_passage": True}
    assert json.loads(seen[0].content)["generationConfig"]["responseMimeType"] == "application/json"


@pytest.mark.parametrize("text", ['["not", "an", "object"]', '{"cut": "off'])
def test_complete_json_rejects_anything_but_an_object(text: str) -> None:  # HAL-001
    client = _client(_answer({"text": text}), [])
    with pytest.raises(ValueError):  # callers turn this into a repair attempt or "insufficient"
        asyncio.run(client.complete_json(_MESSAGES, model="m", schema={}, max_tokens=20))


@pytest.mark.parametrize(
    "response",
    [
        {"promptFeedback": {"blockReason": "SAFETY"}},
        _answer(finish="MAX_TOKENS"),  # thinking used the whole cap
        {},
    ],
)
def test_no_usable_answer_raises_instead_of_returning_empty(response: dict[str, Any]) -> None:
    # HAL-003: an empty answer must surface as a failure, never as a blank "answer".
    client = _client(response, [])
    with pytest.raises(RuntimeError, match="Gemini"):
        asyncio.run(client.complete(_MESSAGES, model="m", max_tokens=20))


def test_selecting_gemini_needs_a_key(monkeypatch: pytest.MonkeyPatch) -> None:  # SEC-001, DR-004
    assert isinstance(get_llm_client(), MockLLMClient)  # the suite's default stays offline
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
            get_llm_client()
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        get_settings.cache_clear()
        assert isinstance(get_llm_client(), GeminiLLMClient)  # PROVIDER_MODE is still mock
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
