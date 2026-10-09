"""Object storage for raw source documents (ING-008).

Raw filings are always preserved so reprocessing never re-downloads. Two backends sit behind one
interface (ADR-0012): `FilesystemObjectStorage` (MVP default, `.storage/`) and
`MinioObjectStorage` (S3-compatible — MinIO locally, AWS S3 in prod). `get_object_storage()`
picks one from config; nothing outside this module changes when the backend switches.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from app.config import Settings, get_settings


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


class MinioObjectStorage(ObjectStorage):
    """S3-compatible backend (MinIO locally, AWS S3 in prod). Encryption-at-rest is a bucket-level
    setting on the managed service (SEC-011), not something this client toggles per object."""

    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool,
    ) -> None:
        from minio import Minio

        self._bucket = bucket
        self._client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
        if not self._client.bucket_exists(bucket):
            self._client.make_bucket(bucket)

    def put(self, key: str, data: bytes) -> str:
        import io

        self._client.put_object(self._bucket, key, io.BytesIO(data), length=len(data))
        return key

    def get(self, key: str) -> bytes:
        response = self._client.get_object(self._bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def exists(self, key: str) -> bool:
        from minio.error import S3Error

        try:
            self._client.stat_object(self._bucket, key)
            return True
        except S3Error:
            return False


def get_object_storage(settings: Settings | None = None) -> ObjectStorage:
    """Return the configured object-storage backend (ADR-0012)."""
    settings = settings or get_settings()
    if settings.object_storage_backend == "s3":
        return MinioObjectStorage(
            endpoint=settings.object_storage_endpoint,
            access_key=settings.object_storage_access_key,
            secret_key=settings.object_storage_secret_key,
            bucket=settings.object_storage_bucket,
            secure=settings.object_storage_secure,
        )
    return FilesystemObjectStorage(settings.storage_dir)
