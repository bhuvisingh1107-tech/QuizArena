"""Future cloud storage backend stub (S3 / R2 / GCS)."""

from typing import Any

from app.storage.base import StorageBackend


class CloudStorageBackend(StorageBackend):
    """Future cloud backend — not active in v1."""

    def upload(
        self,
        data: bytes,
        *,
        category: str,
        extension: str,
        quiz_id: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError("Cloud storage is not available in v1")

    def get_url(self, storage_key: str) -> str:
        raise NotImplementedError("Cloud storage is not available in v1")

    def delete(self, storage_key: str) -> None:
        raise NotImplementedError("Cloud storage is not available in v1")

    def read(self, storage_key: str) -> bytes:
        raise NotImplementedError("Cloud storage is not available in v1")

    def exists(self, storage_key: str) -> bool:
        raise NotImplementedError("Cloud storage is not available in v1")
