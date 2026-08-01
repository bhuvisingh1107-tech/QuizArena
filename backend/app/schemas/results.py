"""Session results and analytics schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RoomState


class ResultsRoomData(BaseModel):
    """Room metadata included in results."""

    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    room_code: str = Field(serialization_alias="roomCode")
    quiz_title_snapshot: str = Field(serialization_alias="quizTitleSnapshot")
    state: RoomState
    started_at: datetime | None = Field(default=None, serialization_alias="startedAt")
    completed_at: datetime | None = Field(default=None, serialization_alias="completedAt")


class ResultsSummaryData(BaseModel):
    """Aggregate session summary."""

    model_config = ConfigDict(populate_by_name=True)

    participant_count: int = Field(serialization_alias="participantCount")
    average_score: float = Field(serialization_alias="averageScore")
    average_accuracy_percent: float = Field(serialization_alias="averageAccuracyPercent")
    total_questions: int = Field(serialization_alias="totalQuestions")
    average_response_time_ms: float | None = Field(
        default=None,
        serialization_alias="averageResponseTimeMs",
    )


class LeaderboardEntryData(BaseModel):
    """Leaderboard / podium row."""

    model_config = ConfigDict(populate_by_name=True)

    rank: int
    participant_id: UUID = Field(serialization_alias="participantId")
    display_name: str = Field(serialization_alias="displayName")
    score: int
    streak: int
    total_correct: int = Field(serialization_alias="totalCorrect")
    total_incorrect: int = Field(serialization_alias="totalIncorrect")
    unanswered_count: int = Field(serialization_alias="unansweredCount")


class PodiumData(BaseModel):
    """Top-three podium entries."""

    model_config = ConfigDict(populate_by_name=True)

    entries: list[LeaderboardEntryData]


class OptionDistributionData(BaseModel):
    """Per-option selection counts for a question."""

    model_config = ConfigDict(populate_by_name=True)

    option_id: UUID = Field(serialization_alias="optionId")
    text: str
    selected_count: int = Field(serialization_alias="selectedCount")
    is_correct: bool = Field(serialization_alias="isCorrect")


class QuestionAnalyticsData(BaseModel):
    """Per-question analytics for a session."""

    model_config = ConfigDict(populate_by_name=True)

    question_id: UUID = Field(serialization_alias="questionId")
    question_index: int = Field(serialization_alias="questionIndex")
    prompt_text: str | None = Field(default=None, serialization_alias="promptText")
    section_name: str = Field(serialization_alias="sectionName")
    submission_count: int = Field(serialization_alias="submissionCount")
    correct_count: int = Field(serialization_alias="correctCount")
    incorrect_count: int = Field(serialization_alias="incorrectCount")
    unanswered_count: int = Field(serialization_alias="unansweredCount")
    accuracy_percent: float = Field(serialization_alias="accuracyPercent")
    average_response_time_ms: float | None = Field(
        default=None,
        serialization_alias="averageResponseTimeMs",
    )
    option_distribution: list[OptionDistributionData] = Field(
        serialization_alias="optionDistribution",
    )


class SectionAnalyticsData(BaseModel):
    """Per-section score analytics."""

    model_config = ConfigDict(populate_by_name=True)

    section_id: UUID = Field(serialization_alias="sectionId")
    name: str
    average_score: float = Field(serialization_alias="averageScore")
    question_count: int = Field(serialization_alias="questionCount")


class ResultsData(BaseModel):
    """GET /live-rooms/{room_id}/results payload."""

    model_config = ConfigDict(populate_by_name=True)

    room: ResultsRoomData
    summary: ResultsSummaryData
    leaderboard: list[LeaderboardEntryData]
    podium: PodiumData
    question_analytics: list[QuestionAnalyticsData] = Field(
        serialization_alias="questionAnalytics",
    )
    section_analytics: list[SectionAnalyticsData] = Field(
        serialization_alias="sectionAnalytics",
    )
