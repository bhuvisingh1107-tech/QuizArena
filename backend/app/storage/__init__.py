"""File storage backends."""

from pathlib import Path

from app.config import Settings
from app.storage.base import StorageBackend
from app.storage.cloud import CloudStorageBackend
from app.storage.local import LocalStorageBackend


def create_storage_backend(settings: Settings) -> StorageBackend:
    """Factory for the configured storage backend (local v1 / cloud future)."""
    if settings.storage_backend == "cloud":
        return CloudStorageBackend()
    root = Path(settings.storage_path)
    if not root.is_absolute():
        # Resolve relative paths from the backend package parent (repo layout).
        root = (Path.cwd() / root).resolve()
    return LocalStorageBackend(root)


__all__ = [
    "CloudStorageBackend",
    "LocalStorageBackend",
    "StorageBackend",
    "create_storage_backend",
]
