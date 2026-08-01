"""Participant data access (DATABASE_SCHEMA.md §7.4)."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.live_room import LiveRoom
from app.models.participant import Participant
from app.models.room_ban import RoomBan


class ParticipantRepository:
    """Repository for participants and room-ban lookups used by join."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        live_room_id: UUID,
        display_name: str,
        email: str,
        session_token: str,
        state,
        connection_status,
    ) -> Participant:
        participant = Participant(
            live_room_id=live_room_id,
            display_name=display_name,
            email=email,
            session_token=session_token,
            state=state,
            connection_status=connection_status,
        )
        self._session.add(participant)
        self._session.flush()
        return participant

    def get_by_id(self, participant_id: UUID) -> Participant | None:
        return self._session.get(Participant, participant_id)

    def get_by_session_token(self, session_token: str) -> Participant | None:
        stmt = (
            select(Participant)
            .options(selectinload(Participant.live_room))
            .where(Participant.session_token == session_token)
        )
        return self._session.scalar(stmt)

    def get_by_room_and_email(self, live_room_id: UUID, email: str) -> Participant | None:
        stmt = select(Participant).where(
            Participant.live_room_id == live_room_id,
            Participant.email == email,
        )
        return self._session.scalar(stmt)

    def get_by_room_and_display_name(
        self,
        live_room_id: UUID,
        display_name: str,
    ) -> Participant | None:
        stmt = select(Participant).where(
            Participant.live_room_id == live_room_id,
            func.lower(Participant.display_name) == display_name.strip().lower(),
        )
        return self._session.scalar(stmt)

    def count_for_room(self, live_room_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(Participant)
            .where(Participant.live_room_id == live_room_id)
        )
        return int(self._session.scalar(stmt) or 0)

    def list_for_room(self, live_room_id: UUID) -> list[Participant]:
        stmt = select(Participant).where(Participant.live_room_id == live_room_id)
        return list(self._session.scalars(stmt).all())

    def get_room_by_code(self, room_code: str) -> LiveRoom | None:
        stmt = select(LiveRoom).where(LiveRoom.room_code == room_code.upper())
        return self._session.scalar(stmt)

    def is_email_banned(self, live_room_id: UUID, email: str) -> bool:
        stmt = select(RoomBan.id).where(
            RoomBan.live_room_id == live_room_id,
            RoomBan.email == email,
        )
        return self._session.scalar(stmt) is not None

    def session_token_exists(self, session_token: str) -> bool:
        stmt = select(Participant.id).where(Participant.session_token == session_token)
        return self._session.scalar(stmt) is not None

    def flush(self) -> None:
        self._session.flush()
