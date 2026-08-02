"""WebSocket connect authentication (SOCKET_EVENTS.md §2–3)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.websocket.events import ClientRole
from app.config import Settings
from app.core.exceptions import AuthenticationError, NotFoundError, ValidationError
from app.core.security import TokenValidationError, validate_access_token
from app.models.enums import RoomState
from app.models.live_room import LiveRoom
from app.models.participant import Participant
from app.services.auth_service import AuthService
from app.services.participant_service import ParticipantService


@dataclass(frozen=True)
class AuthenticatedSocket:
    """Result of a successful WebSocket handshake."""

    role: ClientRole
    room: LiveRoom
    participant: Participant | None = None
    admin_id: UUID | None = None
    is_reconnect: bool = False


def authenticate_websocket(
    *,
    session: Session,
    settings: Settings,
    role: str | None,
    token: str | None,
    room_id: str | None,
) -> AuthenticatedSocket:
    """Validate query-param credentials and resolve the target room."""
    if not role:
        raise ValidationError("VALIDATION_ERROR", "Query parameter 'role' is required")
    try:
        client_role = ClientRole(role.lower())
    except ValueError as exc:
        raise ValidationError(
            "VALIDATION_ERROR",
            "role must be one of: admin, participant, display",
        ) from exc

    if not token:
        raise AuthenticationError("AUTH_ERROR", "Query parameter 'token' is required")

    if client_role == ClientRole.ADMIN:
        return _auth_admin(session, settings, token=token, room_id=room_id)
    if client_role == ClientRole.PARTICIPANT:
        return _auth_participant(session, token=token)
    return _auth_display(session, token=token)


def _auth_admin(
    session: Session,
    settings: Settings,
    *,
    token: str,
    room_id: str | None,
) -> AuthenticatedSocket:
    if not room_id:
        raise ValidationError("VALIDATION_ERROR", "Query parameter 'roomId' is required for admin")
    try:
        room_uuid = UUID(room_id)
    except ValueError as exc:
        raise ValidationError("VALIDATION_ERROR", "Invalid roomId") from exc

    try:
        validate_access_token(token, settings)
    except TokenValidationError as exc:
        raise AuthenticationError(exc.code, exc.message) from exc

    admin = AuthService(session, settings).get_admin_from_token(token)
    room = _get_room(session, room_uuid)
    _ensure_room_connectable(room)
    return AuthenticatedSocket(
        role=ClientRole.ADMIN,
        room=room,
        admin_id=admin.id,
        is_reconnect=False,
    )


def _auth_participant(session: Session, *, token: str) -> AuthenticatedSocket:
    service = ParticipantService(session)
    try:
        participant = service.get_by_token(token)
    except AuthenticationError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise AuthenticationError("AUTH_ERROR", "Invalid participant session token") from exc

    room = participant.live_room
    if room is None:
        room = session.get(LiveRoom, participant.live_room_id)
    if room is None:
        raise NotFoundError("NOT_FOUND", "Live room not found")
    _ensure_room_connectable(room)

    from app.models.enums import ConnectionStatus, ParticipantState

    was_disconnected = (
        participant.state == ParticipantState.DISCONNECTED
        or participant.connection_status == ConnectionStatus.DISCONNECTED
    )
    # Restore presence without inventing quiz state (reuses ParticipantService.reconnect).
    restored, room = service.reconnect(token)
    return AuthenticatedSocket(
        role=ClientRole.PARTICIPANT,
        room=room,
        participant=restored,
        is_reconnect=was_disconnected,
    )


def _auth_display(session: Session, *, token: str) -> AuthenticatedSocket:
    from urllib.parse import unquote

    # Path/query clients may send encoded or padded values; normalize before lookup.
    candidates: list[str] = []
    for raw in (token, unquote(token)):
        normalized = raw.strip()
        if normalized and normalized not in candidates:
            candidates.append(normalized)

    room: LiveRoom | None = None
    for candidate in candidates:
        room = session.scalar(
            select(LiveRoom)
            .options(selectinload(LiveRoom.config))
            .where(LiveRoom.secret_token == candidate),
        )
        if room is not None:
            break

    if room is None:
        raise AuthenticationError("AUTH_ERROR", "Invalid presentation secret token")
    _ensure_room_connectable(room)
    return AuthenticatedSocket(role=ClientRole.DISPLAY, room=room)


def _get_room(session: Session, room_id: UUID) -> LiveRoom:
    room = session.get(LiveRoom, room_id)
    if room is None:
        raise NotFoundError("NOT_FOUND", "Live room not found")
    return room


def _ensure_room_connectable(room: LiveRoom) -> None:
    if room.state == RoomState.CLOSED or room.codes_expired:
        raise ValidationError("ROOM_CLOSED", "Room is closed")
