"""Local filesystem storage backend (SYSTEM_ARCHITECTURE.md §10.4)."""

from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.exceptions import NotFoundError, ValidationError
from app.storage.base import StorageBackend

_CATEGORY_DIRS = {
    "question_image": "images",
    "question_audio": "audio",
    "quiz_branding": "branding/quizzes",
    "platform_branding": "branding/platform",
}


class LocalStorageBackend(StorageBackend):
    """v1 active backend — local directory / Render persistent disk."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        for relative in ("images", "audio", "branding/platform", "branding/quizzes"):
            (self._root / relative).mkdir(parents=True, exist_ok=True)

    def upload(
        self,
        data: bytes,
        *,
        category: str,
        extension: str,
        quiz_id: str | None = None,
    ) -> dict[str, Any]:
        storage_key = self._build_storage_key(category, extension, quiz_id=quiz_id)
        path = self._resolve(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return {"storage_key": storage_key, "size": len(data)}

    def get_url(self, storage_key: str) -> str:
        # Public URL is media-id based; this returns a stable backend locator.
        return f"local://{storage_key}"

    def delete(self, storage_key: str) -> None:
        path = self._resolve(storage_key)
        if path.exists():
            path.unlink()

    def read(self, storage_key: str) -> bytes:
        path = self._resolve(storage_key)
        if not path.exists():
            raise NotFoundError("MEDIA_NOT_FOUND", "Stored media file not found")
        return path.read_bytes()

    def exists(self, storage_key: str) -> bool:
        return self._resolve(storage_key).exists()

    def _build_storage_key(
        self,
        category: str,
        extension: str,
        *,
        quiz_id: str | None,
    ) -> str:
        base = _CATEGORY_DIRS.get(category)
        if base is None:
            raise ValidationError("INVALID_CATEGORY", f"Unknown media category '{category}'")
        ext = extension.lstrip(".").lower()
        file_id = str(uuid4())
        if category == "quiz_branding":
            if not quiz_id:
                raise ValidationError(
                    "QUIZ_ID_REQUIRED",
                    "quizId is required when uploading quiz branding media",
                )
            return f"{base}/{quiz_id}/{file_id}.{ext}"
        return f"{base}/{file_id}.{ext}"

    def _resolve(self, storage_key: str) -> Path:
        # Prevent path traversal: keys must stay under the storage root.
        candidate = (self._root / storage_key).resolve()
        if not str(candidate).startswith(str(self._root)):
            raise ValidationError("INVALID_STORAGE_KEY", "Invalid storage key")
        return candidate
