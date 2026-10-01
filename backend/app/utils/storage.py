"""Object storage for raw source documents (ING-008).

Raw filings are always preserved so reprocessing never re-downloads. This is a filesystem
backend behind an interface; the S3/MinIO backend is wired in deployment (ADR-0012).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class ObjectStorage(ABC):
    @abstractmethod
    def put(self, key: str, data: bytes) -> str:
        """Store `data` at `key`; return the key."""

    @abstractmethod
    def get(self, key: str) -> bytes: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...


class FilesystemObjectStorage(ObjectStorage):
    """Stores objects under a base directory. Keys map to relative paths."""

    def __init__(self, base_dir: str | Path) -> None:
        self._base = Path(base_dir)

    def _path(self, key: str) -> Path:
        # Prevent path traversal outside the base dir.
        resolved = (self._base / key).resolve()
        if not str(resolved).startswith(str(self._base.resolve())):
            raise ValueError(f"invalid storage key: {key!r}")
        return resolved

    def put(self, key: str, data: bytes) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()
