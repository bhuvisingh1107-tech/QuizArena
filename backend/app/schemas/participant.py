"""Participant join / session schemas (API_SPEC.md §12)."""

from datetime import datetime
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from app.models.enums import ConnectionStatus, LobbySubState, ParticipantState, RoomState

_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class JoinRequest(BaseModel):
    """POST /join body — room code + identity."""

    model_config = ConfigDict(populate_by_name=True)

    room_code: str = Field(
        min_length=6,
        max_length=6,
        serialization_alias="roomCode",
        validation_alias=AliasChoices("roomCode", "room_code"),
    )
    display_name: str = Field(
        min_length=1,
        max_length=64,
        serialization_alias="displayName",
        validation_alias=AliasChoices("displayName", "display_name"),
    )
    email: str = Field(
        min_length=3,
        max_length=255,
        pattern=_EMAIL_PATTERN,
    )

    @field_validator("room_code")
    @classmethod
    def normalize_room_code(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if len(cleaned) != 6 or not cleaned.isalnum():
            raise ValueError("Room code must be 6 alphanumeric characters")
        return cleaned

    @field_validator("display_name")
    @classmethod
    def strip_display_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Display name must not be blank")
        return cleaned

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not cleaned:
            raise ValueError("Email must not be blank")
        return cleaned


class ParticipantResponseData(BaseModel):
    """Participant payload (own email visible to self)."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    live_room_id: UUID = Field(serialization_alias="liveRoomId")
    display_name: str = Field(serialization_alias="displayName")
    email: str
    state: ParticipantState
    connection_status: ConnectionStatus = Field(serialization_alias="connectionStatus")
    total_score: int = Field(serialization_alias="totalScore")
    streak: int
    rank: int | None = None
    total_correct: int = Field(default=0, serialization_alias="totalCorrect")
    total_incorrect: int = Field(default=0, serialization_alias="totalIncorrect")
    unanswered_count: int = Field(default=0, serialization_alias="unansweredCount")
    joined_at: datetime = Field(serialization_alias="joinedAt")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class JoinRoomMetaData(BaseModel):
    """Room metadata returned with join / reconnect."""

    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    room_code: str = Field(serialization_alias="roomCode")
    state: RoomState
    lobby_sub_state: LobbySubState | None = Field(
        default=None,
        serialization_alias="lobbySubState",
    )
    quiz_title: str = Field(serialization_alias="quizTitle")
    codes_expired: bool = Field(serialization_alias="codesExpired")


class JoinResponseData(BaseModel):
    """Successful join / reconnect envelope data."""

    model_config = ConfigDict(populate_by_name=True)

    session_token: str = Field(serialization_alias="sessionToken")
    participant: ParticipantResponseData
    room: JoinRoomMetaData
    restored: bool = False


class LeaveResponseData(BaseModel):
    """Graceful leave acknowledgement."""

    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    left: bool = True
    state: ParticipantState


class AdminParticipantItem(BaseModel):
    """Admin participant list row for a live room."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    display_name: str = Field(serialization_alias="displayName")
    email: str
    state: ParticipantState
    connection_status: ConnectionStatus = Field(serialization_alias="connectionStatus")
    total_score: int = Field(serialization_alias="totalScore")
    streak: int
    rank: int | None = None
    total_correct: int = Field(serialization_alias="totalCorrect")
    total_incorrect: int = Field(serialization_alias="totalIncorrect")
    unanswered_count: int = Field(serialization_alias="unansweredCount")
    joined_at: datetime = Field(serialization_alias="joinedAt")


class AdminParticipantListData(BaseModel):
    """GET /live-rooms/{room_id}/participants payload."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[AdminParticipantItem]
    total: int
