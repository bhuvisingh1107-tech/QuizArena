"""WebSocket message schemas (SOCKET_EVENTS.md §4)."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class WSMessage(BaseModel):
    """Canonical WebSocket envelope: type + payload + timestamp."""

    model_config = ConfigDict(populate_by_name=True)

    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=utc_now_iso)

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class WSErrorPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    code: str
    message: str
    details: list[Any] = Field(default_factory=list)


class ConnectionAckPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    connection_id: str = Field(serialization_alias="connectionId")
    role: str
    room_id: UUID = Field(serialization_alias="roomId")
    protocol_version: str = Field(default="1.0", serialization_alias="protocolVersion")
    heartbeat_interval_seconds: int = Field(
        serialization_alias="heartbeatIntervalSeconds",
    )


class ResyncPayload(BaseModel):
    """RESYNC snapshot including optional current-question submission status."""

    model_config = ConfigDict(populate_by_name=True)

    role: str
    room: dict[str, Any]
    participant: dict[str, Any] | None = None
    question: dict[str, Any] | None = None
    submission: dict[str, Any] | None = None
    leaderboard: list[dict[str, Any]] | None = None
    podium: dict[str, Any] | None = None
    participant_count: int | None = Field(default=None, serialization_alias="participantCount")
    timer: dict[str, Any] | None = None


def make_message(event_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return WSMessage(type=event_type, payload=payload or {}).to_json_dict()


def make_error(code: str, message: str, *, details: list[Any] | None = None) -> dict[str, Any]:
    return make_message(
        "error",
        WSErrorPayload(code=code, message=message, details=details or []).model_dump(),
    )
