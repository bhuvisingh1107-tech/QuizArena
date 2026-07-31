"""Upload validation and storage orchestration (SYSTEM_ARCHITECTURE.md §10)."""

from dataclasses import dataclass

from app.config import Settings
from app.core.exceptions import ValidationError
from app.models.enums import MediaCategory
from app.storage import StorageBackend, create_storage_backend

# Architecture §10.2 / DATABASE_SCHEMA.md §8
_CATEGORY_LIMITS: dict[MediaCategory, int] = {
    MediaCategory.QUESTION_IMAGE: 5 * 1024 * 1024,
    MediaCategory.QUESTION_AUDIO: 15 * 1024 * 1024,
    MediaCategory.QUIZ_BRANDING: 2 * 1024 * 1024,
    MediaCategory.PLATFORM_BRANDING: 2 * 1024 * 1024,
}

_IMAGE_CATEGORIES = {
    MediaCategory.QUESTION_IMAGE,
    MediaCategory.QUIZ_BRANDING,
    MediaCategory.PLATFORM_BRANDING,
}
_AUDIO_CATEGORIES = {MediaCategory.QUESTION_AUDIO}

_MIME_TO_EXTENSION: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
}


@dataclass(frozen=True)
class StoredFile:
    """Result of a successful storage write."""

    storage_key: str
    mime_type: str
    file_size: int
    extension: str


class FileStorageService:
    """Validate uploads and delegate byte storage to the configured backend."""

    def __init__(
        self,
        settings: Settings,
        backend: StorageBackend | None = None,
    ) -> None:
        self._settings = settings
        self._backend = backend or create_storage_backend(settings)

    @property
    def backend(self) -> StorageBackend:
        return self._backend

    def validate_and_detect(
        self,
        data: bytes,
        category: MediaCategory,
        *,
        declared_content_type: str | None = None,
    ) -> tuple[str, str]:
        """
        Validate size and magic-byte MIME.

        Returns (mime_type, extension).
        """
        if not data:
            raise ValidationError("MISSING_FILE", "Uploaded file is empty")

        max_size = _CATEGORY_LIMITS[category]
        if len(data) > max_size:
            raise ValidationError(
                "FILE_TOO_LARGE",
                f"File exceeds the maximum size of {max_size} bytes for category '{category.value}'",
            )

        mime_type = detect_mime_type(data)
        if mime_type is None:
            raise ValidationError(
                "UNSUPPORTED_MEDIA_TYPE",
                "Could not determine a supported media type from file contents",
            )

        if category in _IMAGE_CATEGORIES and not mime_type.startswith("image/"):
            raise ValidationError(
                "UNSUPPORTED_MEDIA_TYPE",
                f"Category '{category.value}' requires an image (JPEG, PNG, or WebP)",
            )
        if category in _AUDIO_CATEGORIES and not mime_type.startswith("audio/"):
            raise ValidationError(
                "UNSUPPORTED_MEDIA_TYPE",
                f"Category '{category.value}' requires audio (MP3 or WAV)",
            )

        # Normalize WAV aliases
        if mime_type in {"audio/x-wav", "audio/wave"}:
            mime_type = "audio/wav"

        allowed = allowed_mimes_for_category(category)
        if mime_type not in allowed:
            raise ValidationError(
                "UNSUPPORTED_MEDIA_TYPE",
                f"MIME type '{mime_type}' is not allowed for category '{category.value}'",
            )

        extension = _MIME_TO_EXTENSION[mime_type]
        return mime_type, extension

    def upload(
        self,
        data: bytes,
        category: MediaCategory,
        *,
        quiz_id: str | None = None,
        declared_content_type: str | None = None,
    ) -> StoredFile:
        mime_type, extension = self.validate_and_detect(
            data,
            category,
            declared_content_type=declared_content_type,
        )
        result = self._backend.upload(
            data,
            category=category.value,
            extension=extension,
            quiz_id=quiz_id,
        )
        return StoredFile(
            storage_key=result["storage_key"],
            mime_type=mime_type,
            file_size=len(data),
            extension=extension,
        )

    def delete(self, storage_key: str) -> None:
        self._backend.delete(storage_key)

    def read(self, storage_key: str) -> bytes:
        return self._backend.read(storage_key)


def allowed_mimes_for_category(category: MediaCategory) -> set[str]:
    if category in _IMAGE_CATEGORIES:
        return {"image/jpeg", "image/png", "image/webp"}
    if category in _AUDIO_CATEGORIES:
        return {"audio/mpeg", "audio/wav"}
    return set()


def detect_mime_type(data: bytes) -> str | None:
    """Detect MIME type from magic bytes (not filename extension)."""
    if len(data) < 12:
        # Still allow short JPEG/PNG headers
        if len(data) >= 3 and data[:3] == b"\xff\xd8\xff":
            return "image/jpeg"
        if len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n":
            return "image/png"
        return None

    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "audio/wav"
    if data[:3] == b"ID3":
        return "audio/mpeg"
    # MPEG frame sync
    if data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        return "audio/mpeg"
    return None
