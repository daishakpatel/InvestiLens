"""Live Voyage AI embedding client (Phase 2b, ADR-0010).

Voyage's embeddings endpoint is a single POST returning one vector per input plus token usage,
so a batch of up to 128 texts is one request (EMB-002). The API key is sent as a Bearer header
(never in the URL/logs). `input_type` is `document` at index time and `query` at search time, per
ADR-0010. Vectors come back L2-normalized from Voyage; we normalize defensively anyway so cosine
distance is exact regardless of provider (EMB-001).
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from typing import Any

from app.config import get_settings
from app.providers.base import EmbeddingClient
from app.utils.http import HardenedHttpClient

ALLOWED_HOSTS = frozenset({"api.voyageai.com"})
_ENDPOINT = "https://api.voyageai.com/v1/embeddings"


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


class VoyageEmbeddingClient(EmbeddingClient):
    def __init__(self, client: HardenedHttpClient | None = None) -> None:
        settings = get_settings()
        if client is None and not settings.voyage_api_key:
            raise RuntimeError("VOYAGE_API_KEY is required for live embeddings (ADR-0010)")
        self._model = settings.embedding_model
        self._dim = settings.embedding_dimension
        self._last_total_tokens = 0
        self._http = client or HardenedHttpClient(
            user_agent=settings.sec_user_agent,
            allowed_hosts=ALLOWED_HOSTS,
            rate_per_sec=settings.embedding_rate_limit_per_sec,
            default_headers={
                "Authorization": f"Bearer {settings.voyage_api_key}",
                "Content-Type": "application/json",
            },
        )

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def last_total_tokens(self) -> int:
        """Provider-reported token usage from the most recent `embed` call (EMB-002 cost log)."""
        return self._last_total_tokens

    async def embed(
        self, texts: Sequence[str], *, input_type: str = "document"
    ) -> Sequence[Sequence[float]]:
        if not texts:
            self._last_total_tokens = 0
            return []
        payload = {"input": list(texts), "model": self._model, "input_type": input_type}
        body = self._http.post_bytes(_ENDPOINT, json=payload)
        return self._parse(body, expected=len(texts))

    def _parse(self, body: bytes, *, expected: int) -> list[list[float]]:
        data: dict[str, Any] = json.loads(body)
        rows = sorted(data["data"], key=lambda r: r["index"])  # provider order is not guaranteed
        if len(rows) != expected:
            raise RuntimeError(f"Voyage returned {len(rows)} vectors for {expected} inputs")
        self._last_total_tokens = int(data.get("usage", {}).get("total_tokens", 0))
        return [_normalize([float(x) for x in r["embedding"]]) for r in rows]
