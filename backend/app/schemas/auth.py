"""Authentication request/response schemas (API_SPEC.md §3.1, §7)."""

from __future__ import annotations

from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models.enums import AdminRole


class LoginRequest(BaseModel):
    """POST /admin/login body — ``username`` may be a username or email."""

    model_config = ConfigDict(populate_by_name=True)

    username: str = Field(
        min_length=1,
        max_length=255,
        description="Host username or email",
        validation_alias=AliasChoices("username", "email", "identifier"),
    )
    password: str = Field(min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    """POST /admin/register — create a host account."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str | None = Field(
        default=None,
        max_length=128,
        validation_alias=AliasChoices("confirmPassword", "confirm_password"),
    )

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username may only contain letters, numbers, hyphens, and underscores")
        return cleaned

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Name is required")
        return cleaned

    @model_validator(mode="after")
    def passwords_match(self) -> Self:
        if self.confirm_password is not None and self.confirm_password != self.password:
            raise ValueError("Passwords do not match")
        return self


class LoginResponseData(BaseModel):
    """Successful login payload under ``data``."""

    model_config = ConfigDict(populate_by_name=True)

    access_token: str = Field(serialization_alias="accessToken")
    expires_at: datetime = Field(serialization_alias="expiresAt")


class AdminResponseData(BaseModel):
    """Current authenticated host."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    username: str
    name: str = ""
    email: str | None = None
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
