"""Admin dashboard aggregate counts."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import QuizStatus, RoomState
from app.models.live_room import LiveRoom
from app.models.participant import Participant
from app.models.quiz import Quiz
from app.schemas.dashboard import DashboardSummaryData


_HOSTING_STATES = (
    RoomState.SETUP,
    RoomState.LOBBY,
    RoomState.ACTIVE,
    RoomState.PAUSED,
    RoomState.SECTION_BREAK,
)


class DashboardService:
    """Read-only dashboard summary for the host home screen."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def summary(self, *, owner_id: UUID) -> DashboardSummaryData:
        quiz_counts = dict(
            self._session.execute(
                select(Quiz.status, func.count())
                .where(Quiz.status != QuizStatus.DELETED, Quiz.owner_id == owner_id)
                .group_by(Quiz.status)
            ).all()
        )

        def _quiz(status: QuizStatus) -> int:
            return int(quiz_counts.get(status, 0))

        quizzes_draft = _quiz(QuizStatus.DRAFT)
        quizzes_ready = _quiz(QuizStatus.READY)
        quizzes_in_use = _quiz(QuizStatus.IN_USE)
        quizzes_archived = _quiz(QuizStatus.ARCHIVED)
        quizzes_total = quizzes_draft + quizzes_ready + quizzes_in_use + quizzes_archived

        rooms_active = int(
            self._session.scalar(
                select(func.count())
                .select_from(LiveRoom)
                .join(Quiz, Quiz.id == LiveRoom.quiz_id)
                .where(LiveRoom.state.in_(_HOSTING_STATES), Quiz.owner_id == owner_id)
            )
            or 0
        )
        rooms_completed = int(
            self._session.scalar(
                select(func.count())
                .select_from(LiveRoom)
                .join(Quiz, Quiz.id == LiveRoom.quiz_id)
                .where(LiveRoom.state == RoomState.COMPLETED, Quiz.owner_id == owner_id)
            )
            or 0
        )

        start_of_utc_today = datetime.now(UTC).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        participants_today = int(
            self._session.scalar(
                select(func.count())
                .select_from(Participant)
                .join(LiveRoom, LiveRoom.id == Participant.room_id)
                .join(Quiz, Quiz.id == LiveRoom.quiz_id)
                .where(
                    Participant.joined_at >= start_of_utc_today,
                    Quiz.owner_id == owner_id,
                )
            )
            or 0
        )

        return DashboardSummaryData(
            quizzes_total=quizzes_total,
            quizzes_draft=quizzes_draft,
            quizzes_ready=quizzes_ready,
            quizzes_in_use=quizzes_in_use,
            quizzes_archived=quizzes_archived,
            rooms_active=rooms_active,
            rooms_completed=rooms_completed,
            participants_today=participants_today,
        )
