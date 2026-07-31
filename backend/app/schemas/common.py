"""Shared Pydantic schemas."""

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Meta(BaseModel):
    """Optional response metadata."""

    model_config = ConfigDict(from_attributes=True)

    request_id: str | None = Field(default=None, serialization_alias="requestId")
    cursor: str | None = None
    has_more: bool | None = Field(default=None, serialization_alias="hasMore")


class ErrorDetail(BaseModel):
    """Structured error payload."""

    code: str
    message: str
    details: list[Any] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    """Standard error envelope (API_SPEC.md §4.2)."""

    error: ErrorDetail
    meta: Meta


class DataResponse(BaseModel, Generic[T]):
    """Standard success envelope (API_SPEC.md §2)."""

    data: T
    meta: Meta | None = None


class HealthData(BaseModel):
    """Health check payload."""

    status: str
    database: str
    timestamp: datetime
