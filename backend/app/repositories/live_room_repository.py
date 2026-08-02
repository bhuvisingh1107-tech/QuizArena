"""Live room and session snapshot data access (DATABASE_SCHEMA.md §7)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import RoomState
from app.models.live_room import LiveRoom
from app.models.question import Question
from app.models.quiz import Quiz
from app.models.room_config import RoomConfig
from app.models.section import Section
from app.models.session_option import SessionOption
from app.models.session_question import SessionQuestion
from app.models.session_section import SessionSection


class LiveRoomRepository:
    """Repository for LiveRoom, RoomConfig, and session snapshot entities."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_room(
        self,
        *,
        quiz_id: UUID,
        state: RoomState,
        room_code: str,
        secret_token: str,
        quiz_title_snapshot: str,
        config: RoomConfig,
    ) -> LiveRoom:
        room = LiveRoom(
            quiz_id=quiz_id,
            state=state,
            lobby_sub_state=None,
            room_code=room_code,
            secret_token=secret_token,
            quiz_title_snapshot=quiz_title_snapshot,
            config=config,
        )
        self._session.add(room)
        self._session.flush()
        return room

    def has_hosting_room(self, *, owner_id: UUID | None = None) -> bool:
        """True if any room is in an RS-003 hosting state (optionally for one host)."""
        hosting = [
            RoomState.SETUP,
            RoomState.LOBBY,
            RoomState.ACTIVE,
            RoomState.PAUSED,
            RoomState.SECTION_BREAK,
        ]
        stmt = select(LiveRoom.id).where(LiveRoom.state.in_(hosting))
        if owner_id is not None:
            stmt = stmt.join(Quiz, Quiz.id == LiveRoom.quiz_id).where(Quiz.owner_id == owner_id)
        stmt = stmt.limit(1)
        return self._session.scalar(stmt) is not None

    def list(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        state: RoomState | None = None,
        owner_id: UUID | None = None,
    ) -> tuple[list[LiveRoom], int]:
        filters = []
        if state is not None:
            filters.append(LiveRoom.state == state)

        count_stmt = select(func.count()).select_from(LiveRoom)
        list_stmt = (
            select(LiveRoom)
            .options(
                selectinload(LiveRoom.config),
                selectinload(LiveRoom.session_sections),
                selectinload(LiveRoom.session_questions),
            )
            .order_by(LiveRoom.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        if owner_id is not None:
            count_stmt = count_stmt.join(Quiz, Quiz.id == LiveRoom.quiz_id).where(
                Quiz.owner_id == owner_id,
            )
            list_stmt = list_stmt.join(Quiz, Quiz.id == LiveRoom.quiz_id).where(
                Quiz.owner_id == owner_id,
            )
        for condition in filters:
            count_stmt = count_stmt.where(condition)
            list_stmt = list_stmt.where(condition)

        total = int(self._session.scalar(count_stmt) or 0)
        items = list(self._session.scalars(list_stmt).all())
        return items, total

    def get_by_id(self, room_id: UUID, *, owner_id: UUID | None = None) -> LiveRoom | None:
        stmt = (
            select(LiveRoom)
            .options(
                selectinload(LiveRoom.config),
                selectinload(LiveRoom.session_sections),
                selectinload(LiveRoom.session_questions).selectinload(SessionQuestion.options),
            )
            .where(LiveRoom.id == room_id)
        )
        if owner_id is not None:
            stmt = stmt.join(Quiz, Quiz.id == LiveRoom.quiz_id).where(Quiz.owner_id == owner_id)
        return self._session.scalar(stmt)

    def get_quiz_for_snapshot(
        self,
        quiz_id: UUID,
        *,
        owner_id: UUID | None = None,
    ) -> Quiz | None:
        stmt = (
            select(Quiz)
            .options(
                selectinload(Quiz.config),
                selectinload(Quiz.sections)
                .selectinload(Section.questions)
                .selectinload(Question.options),
            )
            .where(Quiz.id == quiz_id)
        )
        if owner_id is not None:
            stmt = stmt.where(Quiz.owner_id == owner_id)
        return self._session.scalar(stmt)

    def room_code_exists(self, room_code: str) -> bool:
        stmt = select(LiveRoom.id).where(LiveRoom.room_code == room_code)
        return self._session.scalar(stmt) is not None

    def secret_token_exists(self, secret_token: str) -> bool:
        stmt = select(LiveRoom.id).where(LiveRoom.secret_token == secret_token)
        return self._session.scalar(stmt) is not None

    def has_active_rooms_for_quiz(
        self,
        quiz_id: UUID,
        *,
        exclude_room_id: UUID | None = None,
    ) -> bool:
        """True if this quiz has a room that is still running (not Completed/Closed)."""
        hosting = [
            RoomState.SETUP,
            RoomState.LOBBY,
            RoomState.ACTIVE,
            RoomState.PAUSED,
            RoomState.SECTION_BREAK,
        ]
        stmt = select(LiveRoom.id).where(
            LiveRoom.quiz_id == quiz_id,
            LiveRoom.state.in_(hosting),
        )
        if exclude_room_id is not None:
            stmt = stmt.where(LiveRoom.id != exclude_room_id)
        stmt = stmt.limit(1)
        return self._session.scalar(stmt) is not None

    def list_rooms_for_quiz(self, quiz_id: UUID) -> list[LiveRoom]:
        stmt = select(LiveRoom).where(LiveRoom.quiz_id == quiz_id)
        return list(self._session.scalars(stmt).all())

    def count_hosting_rooms(self, *, owner_id: UUID | None = None) -> int:
        hosting = [
            RoomState.SETUP,
            RoomState.LOBBY,
            RoomState.ACTIVE,
            RoomState.PAUSED,
            RoomState.SECTION_BREAK,
        ]
        stmt = (
            select(func.count())
            .select_from(LiveRoom)
            .where(LiveRoom.state.in_(hosting))
        )
        if owner_id is not None:
            stmt = stmt.join(Quiz, Quiz.id == LiveRoom.quiz_id).where(Quiz.owner_id == owner_id)
        return int(self._session.scalar(stmt) or 0)

    def add_session_section(self, section: SessionSection) -> SessionSection:
        self._session.add(section)
        self._session.flush()
        return section

    def add_session_question(self, question: SessionQuestion) -> SessionQuestion:
        self._session.add(question)
        self._session.flush()
        return question

    def add_session_option(self, option: SessionOption) -> SessionOption:
        self._session.add(option)
        self._session.flush()
        return option

    def delete(self, room: LiveRoom) -> None:
        self._session.delete(room)
        self._session.flush()

    def flush(self) -> None:
        self._session.flush()
