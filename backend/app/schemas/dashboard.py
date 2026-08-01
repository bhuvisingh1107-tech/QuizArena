"""Admin dashboard summary schemas."""

from pydantic import BaseModel, ConfigDict, Field


class DashboardSummaryData(BaseModel):
    """GET /dashboard/summary payload."""

    model_config = ConfigDict(populate_by_name=True)

    quizzes_total: int = Field(serialization_alias="quizzesTotal")
    quizzes_draft: int = Field(serialization_alias="quizzesDraft")
    quizzes_ready: int = Field(serialization_alias="quizzesReady")
    quizzes_in_use: int = Field(serialization_alias="quizzesInUse")
    quizzes_archived: int = Field(serialization_alias="quizzesArchived")
    rooms_active: int = Field(serialization_alias="roomsActive")
    rooms_completed: int = Field(serialization_alias="roomsCompleted")
    participants_today: int = Field(serialization_alias="participantsToday")
