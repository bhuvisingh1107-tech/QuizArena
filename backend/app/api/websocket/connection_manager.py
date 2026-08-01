"""Room-scoped WebSocket connection pools (SYSTEM_ARCHITECTURE.md §6.1)."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from app.api.websocket.events import ClientRole
from app.schemas.websocket import make_message

logger = logging.getLogger(__name__)


@dataclass
class WSConnection:
    """A single authenticated WebSocket attachment to a room."""

    websocket: WebSocket
    role: ClientRole
    room_id: UUID
    connection_id: str = field(default_factory=lambda: str(uuid4()))
    participant_id: UUID | None = None
    # Admin JWT retained so mid-session expiry can be re-checked on control events.
    auth_token: str | None = None
    last_pong_at: float = field(default_factory=time.monotonic)
    connected_at: float = field(default_factory=time.monotonic)

    @property
    def is_open(self) -> bool:
        return self.websocket.client_state == WebSocketState.CONNECTED


@dataclass
class RoomConnectionPool:
    """Independent connection set for one live room (never shared across rooms)."""

    room_id: UUID
    admin: WSConnection | None = None
    display: WSConnection | None = None
    participants: dict[UUID, WSConnection] = field(default_factory=dict)

    def all_connections(self) -> list[WSConnection]:
        items: list[WSConnection] = []
        if self.admin is not None:
            items.append(self.admin)
        if self.display is not None:
            items.append(self.display)
        items.extend(self.participants.values())
        return items

    def is_empty(self) -> bool:
        return self.admin is None and self.display is None and not self.participants


class ConnectionManager:
    """Global WebSocket manager: authenticate callers register here for pub/sub."""

    def __init__(self) -> None:
        self._rooms: dict[UUID, RoomConnectionPool] = {}
        self._by_connection_id: dict[str, WSConnection] = {}
        self._lock = threading.RLock()

    def get_room_pool(self, room_id: UUID) -> RoomConnectionPool | None:
        return self._rooms.get(room_id)

    async def connect(self, connection: WSConnection) -> WSConnection | None:
        """Register a connection; returns any replaced duplicate connection."""
        with self._lock:
            pool = self._rooms.get(connection.room_id)
            if pool is None:
                pool = RoomConnectionPool(room_id=connection.room_id)
                self._rooms[connection.room_id] = pool

            replaced: WSConnection | None = None
            if connection.role == ClientRole.ADMIN:
                replaced = pool.admin
                pool.admin = connection
            elif connection.role == ClientRole.DISPLAY:
                replaced = pool.display
                pool.display = connection
            elif connection.role == ClientRole.PARTICIPANT:
                if connection.participant_id is None:
                    raise ValueError("participant_id is required for participant connections")
                replaced = pool.participants.get(connection.participant_id)
                pool.participants[connection.participant_id] = connection
            else:
                raise ValueError(f"Unknown role: {connection.role}")

            self._by_connection_id[connection.connection_id] = connection
            if replaced is not None:
                self._by_connection_id.pop(replaced.connection_id, None)
            return replaced

    async def disconnect(self, connection: WSConnection) -> None:
        with self._lock:
            pool = self._rooms.get(connection.room_id)
            if pool is None:
                self._by_connection_id.pop(connection.connection_id, None)
                return

            if pool.admin is connection:
                pool.admin = None
            elif pool.display is connection:
                pool.display = None
            elif (
                connection.participant_id is not None
                and pool.participants.get(connection.participant_id) is connection
            ):
                del pool.participants[connection.participant_id]

            self._by_connection_id.pop(connection.connection_id, None)
            if pool.is_empty():
                self._rooms.pop(connection.room_id, None)

    async def send_to_connection(
        self,
        connection: WSConnection,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> bool:
        if not connection.is_open:
            return False
        message = make_message(event_type, payload)
        try:
            await connection.websocket.send_json(message)
            return True
        except Exception:
            logger.debug(
                "Failed to send WS message",
                extra={"connection_id": connection.connection_id, "type": event_type},
                exc_info=True,
            )
            return False

    def is_participant_connected(self, room_id: UUID, participant_id: UUID) -> bool:
        pool = self._rooms.get(room_id)
        if pool is None:
            return False
        conn = pool.participants.get(participant_id)
        return conn is not None and conn.is_open

    async def broadcast_to_room(
        self,
        room_id: UUID,
        event_type: str,
        payload: dict[str, Any] | None = None,
        *,
        exclude_connection_id: str | None = None,
    ) -> int:
        pool = self._rooms.get(room_id)
        if pool is None:
            return 0
        sent = 0
        for conn in list(pool.all_connections()):
            if exclude_connection_id and conn.connection_id == exclude_connection_id:
                continue
            if await self.send_to_connection(conn, event_type, payload):
                sent += 1
        return sent

    async def broadcast_to_admin(
        self,
        room_id: UUID,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> int:
        pool = self._rooms.get(room_id)
        if pool is None or pool.admin is None:
            return 0
        return 1 if await self.send_to_connection(pool.admin, event_type, payload) else 0

    async def broadcast_to_participants(
        self,
        room_id: UUID,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> int:
        pool = self._rooms.get(room_id)
        if pool is None:
            return 0
        sent = 0
        for conn in list(pool.participants.values()):
            if await self.send_to_connection(conn, event_type, payload):
                sent += 1
        return sent

    async def broadcast_to_display(
        self,
        room_id: UUID,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> int:
        pool = self._rooms.get(room_id)
        if pool is None or pool.display is None:
            return 0
        return 1 if await self.send_to_connection(pool.display, event_type, payload) else 0

    async def broadcast_to_role(
        self,
        room_id: UUID,
        role: ClientRole,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> int:
        if role == ClientRole.ADMIN:
            return await self.broadcast_to_admin(room_id, event_type, payload)
        if role == ClientRole.DISPLAY:
            return await self.broadcast_to_display(room_id, event_type, payload)
        if role == ClientRole.PARTICIPANT:
            return await self.broadcast_to_participants(room_id, event_type, payload)
        return 0

    async def close_connection(
        self,
        connection: WSConnection,
        *,
        code: int = 1000,
        reason: str = "",
    ) -> None:
        try:
            if connection.is_open:
                await connection.websocket.close(code=code, reason=reason)
        except Exception:
            logger.debug("Error closing websocket", exc_info=True)
        await self.disconnect(connection)

    def iter_all_connections(self) -> list[WSConnection]:
        with self._lock:
            result: list[WSConnection] = []
            for pool in self._rooms.values():
                result.extend(pool.all_connections())
            return result

    def room_count(self) -> int:
        return len(self._rooms)

    def connection_count(self) -> int:
        return len(self._by_connection_id)

    def snapshot_counts(self) -> dict[str, int]:
        with self._lock:
            participants = sum(len(pool.participants) for pool in self._rooms.values())
            admins = sum(1 for pool in self._rooms.values() if pool.admin is not None)
            displays = sum(1 for pool in self._rooms.values() if pool.display is not None)
            return {
                "activeRooms": len(self._rooms),
                "connections": len(self._by_connection_id),
                "participants": participants,
                "admins": admins,
                "displays": displays,
            }

    def reset(self) -> None:
        """Test helper — clear all pools."""
        with self._lock:
            self._rooms.clear()
            self._by_connection_id.clear()


connection_manager = ConnectionManager()
