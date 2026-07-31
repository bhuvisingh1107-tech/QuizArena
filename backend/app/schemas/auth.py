"""Authentication request/response schemas (API_SPEC.md §3.1, §7)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AdminRole


class LoginRequest(BaseModel):
    """POST /admin/login body."""

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class LoginResponseData(BaseModel):
    """Successful login payload under ``data``."""

    model_config = ConfigDict(populate_by_name=True)

    access_token: str = Field(serialization_alias="accessToken")
    expires_at: datetime = Field(serialization_alias="expiresAt")


class AdminResponseData(BaseModel):
    """Current authenticated administrator."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    username: str
    role: AdminRole


class LogoutResponseData(BaseModel):
    """Successful logout acknowledgement."""

    message: str = "Logged out successfully"
