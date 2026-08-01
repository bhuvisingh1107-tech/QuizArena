"""Authentication request/response schemas (API_SPEC.md §3.1, §7)."""

from datetime import datetime
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

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


class ChangePasswordRequest(BaseModel):
    """POST /admin/change-password body."""

    model_config = ConfigDict(populate_by_name=True)

    current_password: str = Field(
        min_length=1,
        max_length=128,
        serialization_alias="currentPassword",
        validation_alias=AliasChoices("currentPassword", "current_password"),
    )
    new_password: str = Field(
        min_length=8,
        max_length=128,
        serialization_alias="newPassword",
        validation_alias=AliasChoices("newPassword", "new_password"),
    )


class ChangePasswordResponseData(BaseModel):
    """Successful password change acknowledgement."""

    message: str = "Password changed successfully"
