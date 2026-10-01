"""Mock EmbeddingClient: deterministic, offline embeddings (Phase 0d, DR-004).

Produces stable pseudo-random unit vectors of the configured dimension (1024, ADR-0010) from a
hash of the text, so retrieval tests are reproducible without calling Voyage.

A `model` salt lets tests simulate a second model producing *different* vectors for the same text
(used to exercise the zero-downtime re-embedding swap, EMB-003). The default salt is empty, so the
default model's vectors are byte-for-byte what earlier phases already depend on.
"""

from __future__ import annotations

import hashlib
import struct
from collections.abc import Sequence

from app.config import get_settings
from app.providers.base import EmbeddingClient

MOCK_MODEL = "mock-embed-v1"


def _vector(text: str, dim: int, *, salt: str = "") -> list[float]:
    # Expand a SHA-256 digest of the (salted) text into `dim` floats, then L2-normalize.
    seed = f"{salt}:{text}" if salt else text
    raw = bytearray()
    counter = 0
    while len(raw) < dim * 4:
        raw += hashlib.sha256(f"{seed}:{counter}".encode()).digest()
        counter += 1
    floats = [struct.unpack("<i", raw[i : i + 4])[0] / 2**31 for i in range(0, dim * 4, 4)]
    norm = sum(f * f for f in floats) ** 0.5 or 1.0
    return [f / norm for f in floats]


class MockEmbeddingClient(EmbeddingClient):
    def __init__(self, *, model: str = MOCK_MODEL) -> None:
        # The default model keeps salt="" so vectors match earlier phases exactly; any other model
        # name salts the hash, yielding a distinct-but-deterministic space for migration tests.
        self._model = model
        self._salt = "" if model == MOCK_MODEL else model

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return get_settings().embedding_dimension

    async def embed(
        self, texts: Sequence[str], *, input_type: str = "document"
    ) -> Sequence[Sequence[float]]:
        dim = self.dimension
        return [_vector(text, dim, salt=self._salt) for text in texts]
