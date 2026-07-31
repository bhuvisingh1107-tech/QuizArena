"""Integration tests for native WebSocket infrastructure (SOCKET_EVENTS.md)."""

from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.websocket import connection_manager, heartbeat
from app.api.websocket.connection_manager import WSConnection
from app.api.websocket.events import ClientRole, ServerEventType
from app.models.enums import QuizStatus
from app.models.quiz import Quiz


def _admin_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _ready_quiz(client: TestClient, admin_token: str, db: Session, title: str) -> str:
    quiz_id = client.post(
        "/api/v1/quizzes",
        headers=_admin_headers(admin_token),
        json={"title": title},
    ).json()["data"]["id"]
    section_id = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections",
        headers=_admin_headers(admin_token),
        json={"name": "R1"},
    ).json()["data"]["id"]
    q_id = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections/{section_id}/questions",
        headers=_admin_headers(admin_token),
        json={"questionType": "Text", "promptText": "Q?"},
    ).json()["data"]["id"]
    for text, correct, order in (("A", True, 0), ("B", False, 1)):
        client.post(
            f"/api/v1/quizzes/{quiz_id}/sections/{section_id}/questions/{q_id}/options",
            headers=_admin_headers(admin_token),
            json={"text": text, "isCorrect": correct, "sortOrder": order},
        )
    row = db.get(Quiz, UUID(quiz_id))
    assert row is not None
    row.status = QuizStatus.READY
    db.commit()
    return quiz_id


def _open_room(client: TestClient, admin_token: str, db: Session, title: str) -> dict:
    quiz_id = _ready_quiz(client, admin_token, db, title)
    room = client.post(
        "/api/v1/live-rooms",
        headers=_admin_headers(admin_token),
        json={"quizId": quiz_id},
    ).json()["data"]
    opened = client.post(
        f"/api/v1/live-rooms/{room['id']}/open-lobby",
        headers=_admin_headers(admin_token),
    ).json()["data"]
    return opened


def _join_participant(client: TestClient, room_code: str, name: str, email: str) -> dict:
    return client.post(
        "/api/v1/join",
        json={"roomCode": room_code, "displayName": name, "email": email},
    ).json()["data"]


def _recv_until(ws, event_type: str, *, limit: int = 10) -> dict:
    for _ in range(limit):
        msg = ws.receive_json()
        if msg.get("type") == event_type:
            return msg
    raise AssertionError(f"Did not receive event type {event_type}")


def test_admin_connect(client: TestClient, admin_token: str, db_session: Session) -> None:
    room = _open_room(client, admin_token, db_session, "WS Admin Room")
    with client.websocket_connect(
        f"/ws?role=admin&token={admin_token}&roomId={room['id']}",
    ) as ws:
        ack = _recv_until(ws, ServerEventType.CONNECTION_ACK)
        assert ack["payload"]["role"] == "admin"
        assert ack["payload"]["roomId"] == room["id"]
        resync = _recv_until(ws, ServerEventType.RESYNC)
        assert resync["payload"]["room"]["state"] == "Lobby"


def test_participant_connect(client: TestClient, admin_token: str, db_session: Session) -> None:
    room = _open_room(client, admin_token, db_session, "WS Participant Room")
    joined = _join_participant(client, room["roomCode"], "Pat", "pat@example.com")
    with client.websocket_connect(
        f"/ws?role=participant&token={joined['sessionToken']}",
    ) as ws:
        ack = _recv_until(ws, ServerEventType.CONNECTION_ACK)
        assert ack["payload"]["role"] == "participant"
        resync = _recv_until(ws, ServerEventType.RESYNC)
        assert resync["payload"]["participant"]["displayName"] == "Pat"


def test_presentation_connect(client: TestClient, admin_token: str, db_session: Session) -> None:
    room = _open_room(client, admin_token, db_session, "WS Display Room")
    with client.websocket_connect(
        f"/ws?role=display&token={room['secretToken']}",
    ) as ws:
        ack = _recv_until(ws, ServerEventType.CONNECTION_ACK)
        assert ack["payload"]["role"] == "display"
        resync = _recv_until(ws, ServerEventType.RESYNC)
        assert resync["payload"]["room"]["roomCode"] == room["roomCode"]


def test_invalid_auth(client: TestClient, admin_token: str, db_session: Session) -> None:
    room = _open_room(client, admin_token, db_session, "WS Bad Auth")
    with client.websocket_connect(
        f"/ws?role=admin&token=not-a-jwt&roomId={room['id']}",
    ) as ws:
        err = ws.receive_json()
        assert err["type"] == "error"
        assert err["payload"]["code"] == "AUTH_ERROR"


def test_invalid_room(client: TestClient, admin_token: str) -> None:
    missing = "00000000-0000-0000-0000-000000000000"
    with client.websocket_connect(
        f"/ws?role=admin&token={admin_token}&roomId={missing}",
    ) as ws:
        err = ws.receive_json()
        assert err["type"] == "error"
        assert err["payload"]["code"] == "NOT_FOUND"


def test_disconnect_cleanup(client: TestClient, admin_token: str, db_session: Session) -> None:
    room = _open_room(client, admin_token, db_session, "WS Cleanup")
    with client.websocket_connect(
        f"/ws?role=admin&token={admin_token}&roomId={room['id']}",
    ) as ws:
        _recv_until(ws, ServerEventType.CONNECTION_ACK)
        _recv_until(ws, ServerEventType.RESYNC)
        assert connection_manager.connection_count() == 1
    assert connection_manager.connection_count() == 0


def test_reconnect_replaces_duplicate(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room = _open_room(client, admin_token, db_session, "WS Reconnect")
    with client.websocket_connect(
        f"/ws?role=admin&token={admin_token}&roomId={room['id']}",
    ) as ws1:
        _recv_until(ws1, ServerEventType.CONNECTION_ACK)
        _recv_until(ws1, ServerEventType.RESYNC)
        with client.websocket_connect(
            f"/ws?role=admin&token={admin_token}&roomId={room['id']}",
        ) as ws2:
            _recv_until(ws2, ServerEventType.CONNECTION_ACK)
            _recv_until(ws2, ServerEventType.RESYNC)
            assert connection_manager.connection_count() == 1
            pool = connection_manager.get_room_pool(UUID(room["id"]))
            assert pool is not None
            assert pool.admin is not None


def test_heartbeat_ping_pong(client: TestClient, admin_token: str, db_session: Session) -> None:
    room = _open_room(client, admin_token, db_session, "WS Heartbeat")
    with client.websocket_connect(
        f"/ws?role=admin&token={admin_token}&roomId={room['id']}",
    ) as ws:
        _recv_until(ws, ServerEventType.CONNECTION_ACK)
        _recv_until(ws, ServerEventType.RESYNC)
        ws.send_json({"type": "ping", "payload": {"n": 1}})
        pong = _recv_until(ws, ServerEventType.PONG)
        assert pong["payload"]["echo"]["n"] == 1
        ws.send_json({"type": "pong", "payload": {}})


def test_room_isolation(client: TestClient, admin_token: str, db_session: Session) -> None:
    """Broadcasts must never cross room boundaries."""
    import asyncio

    from starlette.websockets import WebSocketState

    room_a = _open_room(client, admin_token, db_session, "WS Iso A")
    client.post(f"/api/v1/live-rooms/{room_a['id']}/start", headers=_admin_headers(admin_token))
    client.post(f"/api/v1/live-rooms/{room_a['id']}/end", headers=_admin_headers(admin_token))
    client.post(f"/api/v1/live-rooms/{room_a['id']}/close", headers=_admin_headers(admin_token))
    room_b = _open_room(client, admin_token, db_session, "WS Iso B")

    class FakeWS:
        def __init__(self, bucket: list):
            self.client_state = WebSocketState.CONNECTED
            self.bucket = bucket

        async def send_json(self, data):
            self.bucket.append(data)

    bucket_a: list = []
    bucket_b: list = []
    conn_a = WSConnection(
        websocket=FakeWS(bucket_a),  # type: ignore[arg-type]
        role=ClientRole.ADMIN,
        room_id=UUID(room_a["id"]),
    )
    conn_b = WSConnection(
        websocket=FakeWS(bucket_b),  # type: ignore[arg-type]
        role=ClientRole.ADMIN,
        room_id=UUID(room_b["id"]),
    )

    async def _exercise() -> None:
        await connection_manager.connect(conn_a)
        await connection_manager.connect(conn_b)
        await connection_manager.broadcast_to_room(
            UUID(room_b["id"]),
            ServerEventType.ROOM_STATE_CHANGED,
            {"marker": "only-b"},
        )

    asyncio.run(_exercise())
    assert any(m.get("payload", {}).get("marker") == "only-b" for m in bucket_b)
    assert not any(m.get("payload", {}).get("marker") == "only-b" for m in bucket_a)


def test_multiple_participants(client: TestClient, admin_token: str, db_session: Session) -> None:
    room = _open_room(client, admin_token, db_session, "WS Multi")
    p1 = _join_participant(client, room["roomCode"], "One", "one@example.com")
    p2 = _join_participant(client, room["roomCode"], "Two", "two@example.com")
    with client.websocket_connect(
        f"/ws?role=participant&token={p1['sessionToken']}",
    ) as ws1:
        _recv_until(ws1, ServerEventType.CONNECTION_ACK)
        _recv_until(ws1, ServerEventType.RESYNC)
        with client.websocket_connect(
            f"/ws?role=participant&token={p2['sessionToken']}",
        ) as ws2:
            _recv_until(ws2, ServerEventType.CONNECTION_ACK)
            _recv_until(ws2, ServerEventType.RESYNC)
            pool = connection_manager.get_room_pool(UUID(room["id"]))
            assert pool is not None
            assert len(pool.participants) == 2


def test_broadcasts(client: TestClient, admin_token: str, db_session: Session) -> None:
    room = _open_room(client, admin_token, db_session, "WS Broadcast")
    joined = _join_participant(client, room["roomCode"], "Bee", "bee@example.com")
    with client.websocket_connect(
        f"/ws?role=admin&token={admin_token}&roomId={room['id']}",
    ) as admin_ws:
        _recv_until(admin_ws, ServerEventType.CONNECTION_ACK)
        _recv_until(admin_ws, ServerEventType.RESYNC)
        with client.websocket_connect(
            f"/ws?role=participant&token={joined['sessionToken']}",
        ) as part_ws:
            _recv_until(part_ws, ServerEventType.CONNECTION_ACK)
            _recv_until(part_ws, ServerEventType.RESYNC)
            # Admin may also receive participant:joined
            admin_ws.send_json({"type": "admin:toggle_lobby", "payload": {}})
            # Both should see room state events
            seen_part = False
            for _ in range(5):
                msg = part_ws.receive_json()
                if msg["type"] in {
                    ServerEventType.ROOM_STATE_CHANGED,
                    ServerEventType.ROOM_LOBBY_CLOSED,
                }:
                    seen_part = True
                    break
            assert seen_part


def test_stale_connection_removal(client: TestClient, admin_token: str, db_session: Session) -> None:
    import asyncio
    import time

    from starlette.websockets import WebSocketState

    room = _open_room(client, admin_token, db_session, "WS Stale")

    class FakeWS:
        def __init__(self) -> None:
            self.client_state = WebSocketState.CONNECTED

        async def send_json(self, data):
            return None

        async def close(self, code=1000, reason=""):
            self.client_state = WebSocketState.DISCONNECTED

    conn = WSConnection(
        websocket=FakeWS(),  # type: ignore[arg-type]
        role=ClientRole.DISPLAY,
        room_id=UUID(room["id"]),
    )
    conn.last_pong_at = time.monotonic() - 10_000

    async def _exercise() -> None:
        await connection_manager.connect(conn)
        monitor = heartbeat.HeartbeatMonitor(
            connection_manager,
            interval_seconds=0.01,
            timeout_seconds=1.0,
        )
        await monitor.tick()

    asyncio.run(_exercise())
    assert connection_manager.connection_count() == 0


def test_display_cannot_send_control(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room = _open_room(client, admin_token, db_session, "WS Display Forbid")
    with client.websocket_connect(
        f"/ws?role=display&token={room['secretToken']}",
    ) as ws:
        _recv_until(ws, ServerEventType.CONNECTION_ACK)
        _recv_until(ws, ServerEventType.RESYNC)
        ws.send_json({"type": "admin:start_session", "payload": {}})
        err = _recv_until(ws, ServerEventType.ERROR)
        assert err["payload"]["code"] == "FORBIDDEN"


def test_participant_presence_to_admin(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room = _open_room(client, admin_token, db_session, "WS Presence")
    joined = _join_participant(client, room["roomCode"], "Viz", "viz@example.com")
    with client.websocket_connect(
        f"/ws?role=admin&token={admin_token}&roomId={room['id']}",
    ) as admin_ws:
        _recv_until(admin_ws, ServerEventType.CONNECTION_ACK)
        _recv_until(admin_ws, ServerEventType.RESYNC)
        with client.websocket_connect(
            f"/ws?role=participant&token={joined['sessionToken']}",
        ) as part_ws:
            _recv_until(part_ws, ServerEventType.CONNECTION_ACK)
            _recv_until(part_ws, ServerEventType.RESYNC)
            joined_event = _recv_until(admin_ws, ServerEventType.PARTICIPANT_JOINED)
            assert joined_event["payload"]["displayName"] == "Viz"
            assert "email" in joined_event["payload"]
