"""Realtime lifecycle: lobby open, start, complete must broadcast and sync clients."""

from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.websocket.events import ServerEventType
from app.models.enums import QuizStatus, RoomState
from app.models.quiz import Quiz
from app.services.quiz_execution_service import QuizExecutionService


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
        json={"name": "Main", "sortOrder": 0},
    ).json()["data"]
    q = client.post(
        f"/api/v1/quizzes/{quiz['id']}/sections/{section['id']}/questions",
        headers=_auth(token),
        json={
            "questionType": "Text",
            "promptText": "Q1?",
            "timeLimitSeconds": 30,
        },
    ).json()["data"]
    for text, correct, order in (("Yes", True, 0), ("No", False, 1)):
        client.post(
            f"/api/v1/quizzes/{quiz['id']}/sections/{section['id']}/questions/{q['id']}/options",
            headers=_auth(token),
            json={"text": text, "isCorrect": correct, "sortOrder": order},
        )
    validated = client.post(f"/api/v1/quizzes/{quiz['id']}/validate", headers=_auth(token))
    assert validated.status_code == 200, validated.text
    db_quiz = db.get(Quiz, UUID(quiz["id"]))
    assert db_quiz is not None
    assert db_quiz.status == QuizStatus.READY
    return quiz["id"]


def _recv_until(ws, event_type: str, *, limit: int = 40) -> dict:
    for _ in range(limit):
        msg = ws.receive_json()
        if msg.get("type") == event_type:
            return msg
    raise AssertionError(f"Did not receive {event_type}")


def test_open_lobby_broadcasts_and_start_enables_live_flow(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    quiz_id = _ready_quiz(client, admin_token, db_session, "Realtime Lobby")
    room = client.post(
        "/api/v1/live-rooms",
        headers=_auth(admin_token),
        json={"quizId": quiz_id},
    ).json()["data"]

    with client.websocket_connect(
        f"/ws?role=admin&token={admin_token}&roomId={room['id']}",
    ) as admin_ws:
        _recv_until(admin_ws, ServerEventType.CONNECTION_ACK)
        _recv_until(admin_ws, ServerEventType.RESYNC)

        opened = client.post(
            f"/api/v1/live-rooms/{room['id']}/open-lobby",
            headers=_auth(admin_token),
        )
        assert opened.status_code == 200
        assert opened.json()["data"]["state"] == "Lobby"

        lobby_event = _recv_until(admin_ws, ServerEventType.ROOM_LOBBY_OPENED)
        assert lobby_event["payload"]["state"] == "Lobby"

        join = client.post(
            "/api/v1/join",
            json={
                "roomCode": room["roomCode"],
                "displayName": "Pat",
                "email": "pat-realtime@example.com",
            },
        )
        assert join.status_code == 201, join.text
        joined = join.json()["data"]

        with client.websocket_connect(
            f"/ws?role=participant&token={joined['sessionToken']}",
        ) as pws:
            _recv_until(pws, ServerEventType.CONNECTION_ACK)
            resync = _recv_until(pws, ServerEventType.RESYNC)
            assert resync["payload"]["room"]["state"] == "Lobby"

            started = client.post(
                f"/api/v1/live-rooms/{room['id']}/start",
                headers=_auth(admin_token),
            )
            assert started.status_code == 200
            assert started.json()["data"]["state"] == "Active"

            _recv_until(pws, ServerEventType.ROOM_SESSION_STARTED)
            question = _recv_until(pws, ServerEventType.QUESTION_STARTED)
            option_ids = [o["id"] for o in question["payload"]["question"]["options"]]

            pws.send_json(
                {"type": "answer:submit", "payload": {"optionIds": [option_ids[0]]}},
            )
            accepted = _recv_until(pws, ServerEventType.ANSWER_ACCEPTED)
            assert accepted["payload"]["status"] == "submitted"

            ended = client.post(
                f"/api/v1/live-rooms/{room['id']}/end",
                headers=_auth(admin_token),
            )
            assert ended.status_code == 200
            assert ended.json()["data"]["state"] == "Completed"

            completed = _recv_until(pws, ServerEventType.QUIZ_COMPLETED)
            assert completed["payload"]["state"] == "Completed"
            assert completed["payload"].get("podium") is not None

            db_session.expire_all()
            room_row = QuizExecutionService(db_session).get_execution_state(UUID(room["id"])).room
            assert room_row.state == RoomState.COMPLETED
