"""Participant answer response data access (DATABASE_SCHEMA.md §7.5)."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.response import Response


class ResponseRepository:
    """Persistence for per-question participant responses."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_participant_and_question(
        self,
        participant_id: UUID,
        session_question_id: UUID,
    ) -> Response | None:
        stmt = select(Response).where(
            Response.participant_id == participant_id,
            Response.session_question_id == session_question_id,
        )
        return self._session.scalar(stmt)

    def create(self, response: Response) -> Response:
        self._session.add(response)
        self._session.flush()
        return response

    def list_for_question(self, session_question_id: UUID) -> list[Response]:
        stmt = select(Response).where(Response.session_question_id == session_question_id)
        return list(self._session.scalars(stmt).all())

    def count_submitted_for_question(self, session_question_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(Response)
            .where(
                Response.session_question_id == session_question_id,
                Response.is_unanswered.is_(False),
                Response.submitted_at.is_not(None),
            )
        )
        return int(self._session.scalar(stmt) or 0)

    def flush(self) -> None:
        self._session.flush()
