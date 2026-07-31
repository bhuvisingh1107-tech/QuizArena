"""Abstract file storage interface (SYSTEM_ARCHITECTURE.md §10.1)."""

from abc import ABC, abstractmethod
from typing import Any


class StorageBackend(ABC):
    """Abstract storage interface for local and future cloud backends."""

    @abstractmethod
    def upload(
        self,
        data: bytes,
        *,
        category: str,
        extension: str,
        quiz_id: str | None = None,
    ) -> dict[str, Any]:
        """Persist bytes and return a stored file reference (includes storage_key)."""

    @abstractmethod
    def get_url(self, storage_key: str) -> str:
        """Return a backend-relative public path for a stored file."""

    @abstractmethod
    def delete(self, storage_key: str) -> None:
        """Delete a stored file. No-op if missing."""

    @abstractmethod
    def read(self, storage_key: str) -> bytes:
        """Read stored file bytes."""

    @abstractmethod
    def exists(self, storage_key: str) -> bool:
        """Return whether the object exists."""
