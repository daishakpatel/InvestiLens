"""Mock EmbeddingClient: deterministic, offline embeddings (Phase 0d, DR-004).

Produces stable pseudo-random unit vectors of the configured dimension (1024, ADR-0010) from a
hash of the text, so retrieval tests are reproducible without calling Voyage.
"""

from __future__ import annotations

import hashlib
import struct
from collections.abc import Sequence

from app.config import get_settings
from app.providers.base import EmbeddingClient


def _vector(text: str, dim: int) -> list[float]:
    # Expand a SHA-256 digest of the text into `dim` floats, then L2-normalize.
    raw = bytearray()
    counter = 0
    while len(raw) < dim * 4:
        raw += hashlib.sha256(f"{text}:{counter}".encode()).digest()
        counter += 1
    floats = [struct.unpack("<i", raw[i : i + 4])[0] / 2**31 for i in range(0, dim * 4, 4)]
    norm = sum(f * f for f in floats) ** 0.5 or 1.0
    return [f / norm for f in floats]


class MockEmbeddingClient(EmbeddingClient):
    @property
    def dimension(self) -> int:
        return get_settings().embedding_dimension

    async def embed(
        self, texts: Sequence[str], *, input_type: str = "document"
    ) -> Sequence[Sequence[float]]:
        dim = self.dimension
        return [_vector(text, dim) for text in texts]
