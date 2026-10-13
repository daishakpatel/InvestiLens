"""Live Google Gemini LLM client (ADR-0032).

One `generateContent` POST per call through the shared hardened client (timeout, retry with
backoff, circuit breaker, host allowlist). The API key is sent in the `x-goog-api-key` header,
never in the URL, so it cannot reach logs.

Two Gemini behaviours shape this client:

- Thinking tokens count against `maxOutputTokens`, so a caller's small cap (the filing-diff
  adjudicator asks for 20) would be spent before any answer is written. Thinking is kept low and
  the cap is raised by a fixed allowance.
- Schema mode rejects object schemas without properties, which is what report sections pass
  (`items: {"type": "object"}`). JSON mode is used instead: the prompts already state the shape
  and every caller validates what comes back.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Sequence
from typing import Any

from app.config import get_settings
from app.providers.base import LLMClient, LLMMessage
from app.utils.http import HardenedHttpClient
from app.utils.logging import get_logger, log_event

logger = get_logger(__name__)

ALLOWED_HOSTS = frozenset({"generativelanguage.googleapis.com"})
_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_TIMEOUT_S = 60.0  # a 1,500-token report section plus thinking outlasts the shared 20 s default
# shortcut: fixed thinking allowance on top of the caller's cap, raise it if calls end MAX_TOKENS
THINKING_ALLOWANCE_TOKENS = 2048
# Gemini's smaller models cite their own way, whatever marker the prompt asks for: `[cite: a, b]`,
# `[SOURCE:a, SOURCE:b]`, or `[source_id=a]` copied from the evidence labels. Only the syntax is
# rewritten to one `[SOURCE:id]` each; the IDs are still checked against the evidence set
# downstream (CIT-001).
_LABEL = r"(?:cite|source_id|source)\s*[:=]\s*"
_GROUPED = re.compile(rf"\[{_LABEL}([^\]]+)\]", re.IGNORECASE)
_PREFIX = re.compile(rf"^{_LABEL}", re.IGNORECASE)


def _source_markers(text: str) -> str:
    def split(match: re.Match[str]) -> str:
        ids = (_PREFIX.sub("", part.strip()) for part in match.group(1).split(","))
        return "".join(f"[SOURCE:{i}]" for i in ids if i)

    return _GROUPED.sub(split, text)


def _text(data: dict[str, Any]) -> tuple[str, str]:
    """The answer text and its finish reason; raises when the model gave no usable answer."""
    blocked = data.get("promptFeedback", {}).get("blockReason")
    if blocked:
        raise RuntimeError(f"Gemini blocked the prompt: {blocked}")
    candidate = (data.get("candidates") or [{}])[0]
    finish = str(candidate.get("finishReason", "UNKNOWN"))
    parts = candidate.get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    if not text.strip():
        raise RuntimeError(f"Gemini returned no text (finishReason={finish})")
    return text, finish


class GeminiLLMClient(LLMClient):
    def __init__(self, client: HardenedHttpClient | None = None) -> None:
        settings = get_settings()
        if client is None and not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is required for the Gemini LLM client (ADR-0032)")
        self._thinking_level = settings.llm_thinking_level
        self._http = client or HardenedHttpClient(
            user_agent=settings.sec_user_agent,
            allowed_hosts=ALLOWED_HOSTS,
            rate_per_sec=settings.llm_rate_limit_per_sec,
            timeout=_TIMEOUT_S,
            max_retries=2,
            default_headers={
                "x-goog-api-key": settings.gemini_api_key,
                "Content-Type": "application/json",
            },
        )

    async def complete(self, messages: Sequence[LLMMessage], *, model: str, max_tokens: int) -> str:
        return _source_markers(
            self._generate(messages, model=model, max_tokens=max_tokens, json_mode=False)
        )

    async def complete_json(
        self,
        messages: Sequence[LLMMessage],
        *,
        model: str,
        schema: dict[str, Any],
        max_tokens: int,
    ) -> dict[str, Any]:
        text = self._generate(messages, model=model, max_tokens=max_tokens, json_mode=True)
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("Gemini returned JSON that is not an object")
        return parsed

    def _generate(
        self, messages: Sequence[LLMMessage], *, model: str, max_tokens: int, json_mode: bool
    ) -> str:
        config: dict[str, Any] = {"maxOutputTokens": max_tokens + THINKING_ALLOWANCE_TOKENS}
        if self._thinking_level != "default":
            config["thinkingConfig"] = {"thinkingLevel": self._thinking_level}
        if json_mode:
            config["responseMimeType"] = "application/json"
        payload: dict[str, Any] = {
            "contents": [
                {
                    "role": "model" if m.role == "assistant" else "user",
                    "parts": [{"text": m.content}],
                }
                for m in messages
                if m.role != "system"
            ],
            "generationConfig": config,
        }
        system = "\n\n".join(m.content for m in messages if m.role == "system")
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}

        started = time.monotonic()
        outcome = "error"
        usage: dict[str, Any] = {}
        try:
            data = json.loads(self._http.post_bytes(_ENDPOINT.format(model=model), json=payload))
            usage = data.get("usageMetadata", {})
            text, outcome = _text(data)
            return text
        finally:
            log_event(
                logger,
                logging.INFO,
                "llm.call",
                provider="gemini",
                model=model,
                outcome=outcome,
                latency_ms=int((time.monotonic() - started) * 1000),
                # Named without "token": the log redactor blanks any field whose key contains it.
                usage_in=usage.get("promptTokenCount"),
                usage_out=usage.get("candidatesTokenCount"),
                usage_thinking=usage.get("thoughtsTokenCount"),
            )
