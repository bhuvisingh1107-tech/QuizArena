"""Domain exception classes (implementation deferred)."""

from typing import Any


class QuizArenaError(Exception):
    """Base exception for QuizArena domain errors."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: list[Any] | None = None,
        status_code: int = 422,
    ) -> None:
        self.code = code
        self.message = message
        self.details = details or []
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(QuizArenaError):
    """Resource not found."""

    def __init__(self, code: str, message: str, *, details: list[Any] | None = None) -> None:
        super().__init__(code, message, details=details, status_code=404)


class AuthenticationError(QuizArenaError):
    """Authentication failure."""

    def __init__(self, code: str, message: str, *, details: list[Any] | None = None) -> None:
        super().__init__(code, message, details=details, status_code=401)


class AuthorizationError(QuizArenaError):
    """Authorization failure."""

    def __init__(self, code: str, message: str, *, details: list[Any] | None = None) -> None:
        super().__init__(code, message, details=details, status_code=403)


class ConflictError(QuizArenaError):
    """Conflict / duplicate resource."""

    def __init__(self, code: str, message: str, *, details: list[Any] | None = None) -> None:
        super().__init__(code, message, details=details, status_code=409)


class ValidationError(QuizArenaError):
    """Business rule or validation failure."""

    def __init__(self, code: str, message: str, *, details: list[Any] | None = None) -> None:
        super().__init__(code, message, details=details, status_code=422)
