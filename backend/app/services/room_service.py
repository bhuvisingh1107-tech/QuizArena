"""Live room creation, state machine, session control."""

from app.services.live_room_service import LiveRoomService

# Architecture name alias (SYSTEM_ARCHITECTURE.md §4.3 Room Service).
RoomService = LiveRoomService

__all__ = ["LiveRoomService", "RoomService"]
