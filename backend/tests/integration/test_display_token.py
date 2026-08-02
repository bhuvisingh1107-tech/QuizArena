"""Display presentation token: create → URL → WebSocket auth must agree."""

from __future__ import annotations

from urllib.parse import unquote, urlparse
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.websocket.events import ServerEventType
from app.models.enums import QuizStatus
from app.models.live_room import LiveRoom
from app.models.quiz import Quiz


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _ready_quiz(client: TestClient, token: str, db: Session, title: str) -> str:
    quiz = client.post(
        "/api/v1/quizzes",
        headers=_auth(token),
        json={"title": title},
    ).json()["data"]
    section = client.post(
        f"/api/v1/quizzes/{quiz['id']}/sections",
        headers=_auth(token),
        json={"name": "Main"},
    ).json()["data"]
    q = client.post(
        f"/api/v1/quizzes/{quiz['id']}/sections/{section['id']}/questions",
        headers=_auth(token),
        json={"questionType": "Text", "promptText": "Q1?", "timeLimitSeconds": 20},
    ).json()["data"]
    for text, correct, order in (("Yes", True, 0), ("No", False, 1)):
        client.post(
            f"/api/v1/quizzes/{quiz['id']}/sections/{section['id']}/questions/{q['id']}/options",
            headers=_auth(token),
            json={"text": text, "isCorrect": correct, "sortOrder": order},
        )
    assert client.post(
        f"/api/v1/quizzes/{quiz['id']}/validate",
        headers=_auth(token),
    ).status_code == 200
    row = db.get(Quiz, UUID(quiz["id"]))
    assert row is not None
    assert row.status == QuizStatus.READY
    return quiz["id"]


def _recv_until(ws, event_type: str, *, limit: int = 30) -> dict:
    for _ in range(limit):
        msg = ws.receive_json()
        if msg.get("type") == event_type:
            return msg
    raise AssertionError(f"Did not receive {event_type}")


def test_display_url_token_matches_db_and_websocket_auth(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    quiz_id = _ready_quiz(client, admin_token, db_session, "Display Token Room")
    created = client.post(
        "/api/v1/live-rooms",
        headers=_auth(admin_token),
        json={"quizId": quiz_id},
    )
    assert created.status_code == 201, created.text
    room = created.json()["data"]

    secret = room["secretToken"]
    display_url = room["displayUrl"]
    path_token = unquote(urlparse(display_url).path.rstrip("/").split("/")[-1])
    assert path_token == secret

    db_session.expire_all()
    row = db_session.get(LiveRoom, UUID(room["id"]))
    assert row is not None
    assert row.secret_token == secret

    with client.websocket_connect(f"/ws?role=display&token={secret}") as ws:
        ack = _recv_until(ws, ServerEventType.CONNECTION_ACK)
        assert ack["payload"]["role"] == "display"
        resync = _recv_until(ws, ServerEventType.RESYNC)
        assert resync["payload"]["room"]["roomCode"] == room["roomCode"]
        assert resync["payload"]["room"]["state"] == "Setup"

    # Open lobby → display must receive lobby event while connected.
    with client.websocket_connect(f"/ws?role=display&token={secret}") as ws:
        _recv_until(ws, ServerEventType.CONNECTION_ACK)
        _recv_until(ws, ServerEventType.RESYNC)
        opened = client.post(
            f"/api/v1/live-rooms/{room['id']}/open-lobby",
            headers=_auth(admin_token),
        )
        assert opened.status_code == 200
        lobby = _recv_until(ws, ServerEventType.ROOM_LOBBY_OPENED)
        assert lobby["payload"]["state"] == "Lobby"
