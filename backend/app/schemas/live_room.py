"""Live room request/response schemas (API_SPEC.md §11)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.models.enums import (
    AnswerRevealBehavior,
    LobbySubState,
    QuestionAdvanceMode,
    RoomState,
)


def _alias(*names: str) -> AliasChoices:
    return AliasChoices(*names)


class RoomConfigData(BaseModel):
    """Room configuration snapshot / update payload."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    question_advance_mode: QuestionAdvanceMode | None = Field(
        default=None,
        serialization_alias="questionAdvanceMode",
        validation_alias=_alias("questionAdvanceMode", "question_advance_mode"),
    )
    answer_reveal_behavior: AnswerRevealBehavior | None = Field(
        default=None,
        serialization_alias="answerRevealBehavior",
        validation_alias=_alias("answerRevealBehavior", "answer_reveal_behavior"),
    )
    time_bonus_enabled: bool | None = Field(
        default=None,
        serialization_alias="timeBonusEnabled",
        validation_alias=_alias("timeBonusEnabled", "time_bonus_enabled"),
    )
    time_bonus_max_points: int | None = Field(
        default=None,
        ge=0,
        serialization_alias="timeBonusMaxPoints",
        validation_alias=_alias("timeBonusMaxPoints", "time_bonus_max_points"),
    )
    streak_bonus_enabled: bool | None = Field(
        default=None,
        serialization_alias="streakBonusEnabled",
        validation_alias=_alias("streakBonusEnabled", "streak_bonus_enabled"),
    )
    streak_bonus_rules: dict[str, Any] | None = Field(
        default=None,
        serialization_alias="streakBonusRules",
        validation_alias=_alias("streakBonusRules", "streak_bonus_rules"),
    )
    question_order_shuffle: bool | None = Field(
        default=None,
        serialization_alias="questionOrderShuffle",
        validation_alias=_alias("questionOrderShuffle", "question_order_shuffle"),
    )
    answer_option_shuffle: bool | None = Field(
        default=None,
        serialization_alias="answerOptionShuffle",
        validation_alias=_alias("answerOptionShuffle", "answer_option_shuffle"),
    )


class RoomConfigResponseData(BaseModel):
    """Full room config as stored on the session."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    question_advance_mode: QuestionAdvanceMode = Field(serialization_alias="questionAdvanceMode")
    answer_reveal_behavior: AnswerRevealBehavior = Field(
        serialization_alias="answerRevealBehavior",
    )
    time_bonus_enabled: bool = Field(serialization_alias="timeBonusEnabled")
    time_bonus_max_points: int = Field(serialization_alias="timeBonusMaxPoints")
    streak_bonus_enabled: bool = Field(serialization_alias="streakBonusEnabled")
    streak_bonus_rules: dict[str, Any] | None = Field(
        default=None,
        serialization_alias="streakBonusRules",
    )
    question_order_shuffle: bool = Field(serialization_alias="questionOrderShuffle")
    answer_option_shuffle: bool = Field(serialization_alias="answerOptionShuffle")


class LiveRoomCreateRequest(BaseModel):
    """POST /live-rooms body."""

    model_config = ConfigDict(populate_by_name=True)

    quiz_id: UUID = Field(
        serialization_alias="quizId",
        validation_alias=_alias("quizId", "quiz_id"),
    )
    config: RoomConfigData | None = None


class LiveRoomResponseData(BaseModel):
    """Live room control / detail payload."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    quiz_id: UUID = Field(serialization_alias="quizId")
    state: RoomState
    lobby_sub_state: LobbySubState | None = Field(
        default=None,
        serialization_alias="lobbySubState",
    )
    room_code: str = Field(serialization_alias="roomCode")
    secret_token: str = Field(serialization_alias="secretToken")
    quiz_title_snapshot: str = Field(serialization_alias="quizTitleSnapshot")
    current_question_index: int | None = Field(
        default=None,
        serialization_alias="currentQuestionIndex",
    )
    codes_expired: bool = Field(serialization_alias="codesExpired")
    awaiting_host_advance: bool = Field(
        default=False,
        serialization_alias="awaitingHostAdvance",
    )
    join_url: str = Field(serialization_alias="joinUrl")
    display_url: str = Field(serialization_alias="displayUrl")
    qr_target: str = Field(serialization_alias="qrTarget")
    config: RoomConfigResponseData | None = None
    section_count: int = Field(default=0, serialization_alias="sectionCount")
    question_count: int = Field(default=0, serialization_alias="questionCount")
    started_at: datetime | None = Field(default=None, serialization_alias="startedAt")
    completed_at: datetime | None = Field(default=None, serialization_alias="completedAt")
    closed_at: datetime | None = Field(default=None, serialization_alias="closedAt")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class LiveRoomListData(BaseModel):
    """Paginated live room list."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[LiveRoomResponseData]
    total: int


class LiveRoomDeleteData(BaseModel):
    """Delete acknowledgement."""

    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    deleted: bool = True
