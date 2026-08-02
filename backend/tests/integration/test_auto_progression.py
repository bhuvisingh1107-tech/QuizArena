"""Integration tests for automatic live progression, pause/resume, and reveal broadcast."""

from __future__ import annotations

import time
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.websocket.events import ServerEventType
from app.models.enums import QuizStatus, SessionQuestionState
from app.models.quiz import Quiz
from app.services.quiz_execution_service import QuizExecutionService
from app.services.timer_service import auto_progression


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
    for prompt in ("Q1?", "Q2?"):
        q = client.post(
            f"/api/v1/quizzes/{quiz['id']}/sections/{section['id']}/questions",
            headers=_auth(token),
            json={
                "questionType": "Text",
                "promptText": prompt,
                "timeLimitSeconds": 2,
                "explanation": f"Because {prompt}",
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


def _recv_until(ws, event_type: str, *, limit: int = 60) -> dict:
    for _ in range(limit):
        msg = ws.receive_json()
        if msg.get("type") == event_type:
            return msg
    raise AssertionError(f"Did not receive {event_type}")


def test_start_quiz_opens_first_question_and_schedules(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    quiz_id = _ready_quiz(client, admin_token, db_session, "Auto Start")
    room = client.post(
        "/api/v1/live-rooms",
        headers=_auth(admin_token),
        json={"quizId": quiz_id},
    ).json()["data"]
    client.post(f"/api/v1/live-rooms/{room['id']}/open-lobby", headers=_auth(admin_token))

    with client.websocket_connect(
        f"/ws?role=admin&token={admin_token}&roomId={room['id']}",
    ) as ws:
        _recv_until(ws, ServerEventType.CONNECTION_ACK)
        _recv_until(ws, ServerEventType.RESYNC)

        started = client.post(
            f"/api/v1/live-rooms/{room['id']}/start",
            headers=_auth(admin_token),
        )
        assert started.status_code == 200, started.text
        _recv_until(ws, ServerEventType.ROOM_SESSION_STARTED)
        question = _recv_until(ws, ServerEventType.QUESTION_STARTED)
        assert question["payload"]["question"]["state"] == "Open"
        assert question["payload"]["question"]["promptText"] == "Q1?"

    db_session.expire_all()
    state = QuizExecutionService(db_session).get_execution_state(UUID(room["id"]))
    assert state.question is not None
    assert state.question.state == SessionQuestionState.OPEN
    auto_progression.cancel_room(UUID(room["id"]))


def test_all_answered_triggers_auto_reveal(
    client: TestClient,
    admin_token: str,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.timer_service.REVEAL_DWELL_SECONDS", 0.15)
    monkeypatch.setattr("app.services.timer_service.LEADERBOARD_DWELL_SECONDS", 0.05)

    quiz_id = _ready_quiz(client, admin_token, db_session, "Auto Reveal")
    room = client.post(
        "/api/v1/live-rooms",
        headers=_auth(admin_token),
        json={"quizId": quiz_id},
    ).json()["data"]
    client.post(f"/api/v1/live-rooms/{room['id']}/open-lobby", headers=_auth(admin_token))
    join = client.post(
        "/api/v1/join",
        json={
            "roomCode": room["roomCode"],
            "displayName": "Pat",
            "email": "pat@example.com",
        },
    )
    assert join.status_code == 201, join.text
    joined = join.json()["data"]
    client.post(f"/api/v1/live-rooms/{room['id']}/start", headers=_auth(admin_token))

    db_session.expire_all()
    exec_state = QuizExecutionService(db_session).get_execution_state(UUID(room["id"]))
    assert exec_state.question is not None
    option_ids = [
        str(o.id) for o in sorted(exec_state.question.options, key=lambda o: o.sort_order)
    ]

    with client.websocket_connect(
        f"/ws?role=participant&token={joined['sessionToken']}",
    ) as pws:
        _recv_until(pws, ServerEventType.CONNECTION_ACK)
        _recv_until(pws, ServerEventType.RESYNC)

        pws.send_json({"type": "answer:submit", "payload": {"optionIds": [option_ids[0]]}})
        _recv_until(pws, "answer:accepted")
        reveal = _recv_until(pws, ServerEventType.QUESTION_REVEAL)
        assert reveal["payload"]["question"]["state"] in {"Revealed", "Scored"}
        personal = _recv_until(pws, "score:personal")
        assert personal["payload"]["isCorrect"] is True
        auto_progression.cancel_room(UUID(room["id"]))


def test_pause_cancels_and_resume_reschedules(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    quiz_id = _ready_quiz(client, admin_token, db_session, "Pause Resume")
    room = client.post(
        "/api/v1/live-rooms",
        headers=_auth(admin_token),
        json={"quizId": quiz_id},
    ).json()["data"]
    room_id = UUID(room["id"])
    client.post(f"/api/v1/live-rooms/{room['id']}/open-lobby", headers=_auth(admin_token))
    client.post(f"/api/v1/live-rooms/{room['id']}/start", headers=_auth(admin_token))

    time.sleep(0.05)
    assert room_id in auto_progression._tasks

    paused = client.post(f"/api/v1/live-rooms/{room['id']}/pause", headers=_auth(admin_token))
    assert paused.status_code == 200
    time.sleep(0.05)
    assert room_id not in auto_progression._tasks

    resumed = client.post(f"/api/v1/live-rooms/{room['id']}/resume", headers=_auth(admin_token))
    assert resumed.status_code == 200
    time.sleep(0.05)
    assert room_id in auto_progression._tasks

    auto_progression.cancel_room(room_id)


def test_emergency_skip_advances(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    quiz_id = _ready_quiz(client, admin_token, db_session, "Skip Q")
    room = client.post(
        "/api/v1/live-rooms",
        headers=_auth(admin_token),
        json={"quizId": quiz_id},
    ).json()["data"]
    client.post(f"/api/v1/live-rooms/{room['id']}/open-lobby", headers=_auth(admin_token))
    client.post(f"/api/v1/live-rooms/{room['id']}/start", headers=_auth(admin_token))

    with client.websocket_connect(
        f"/ws?role=admin&token={admin_token}&roomId={room['id']}",
    ) as ws:
        _recv_until(ws, ServerEventType.CONNECTION_ACK)
        _recv_until(ws, ServerEventType.RESYNC)
        ws.send_json({"type": "admin:skip", "payload": {}})
        # May receive closed/reveal before next started
        next_q = _recv_until(ws, ServerEventType.QUESTION_STARTED)
        assert next_q["payload"]["question"]["promptText"] == "Q2?"
        auto_progression.cancel_room(UUID(room["id"]))


def test_timer_expiry_auto_advances(
    client: TestClient,
    admin_token: str,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.timer_service.REVEAL_DWELL_SECONDS", 0.1)
    monkeypatch.setattr("app.services.timer_service.LEADERBOARD_DWELL_SECONDS", 0.05)

    quiz_id = _ready_quiz(client, admin_token, db_session, "Timer Advance")
    room = client.post(
        "/api/v1/live-rooms",
        headers=_auth(admin_token),
        json={"quizId": quiz_id},
    ).json()["data"]
    client.post(f"/api/v1/live-rooms/{room['id']}/open-lobby", headers=_auth(admin_token))

    with client.websocket_connect(
        f"/ws?role=admin&token={admin_token}&roomId={room['id']}",
    ) as ws:
        _recv_until(ws, ServerEventType.CONNECTION_ACK)
        _recv_until(ws, ServerEventType.RESYNC)
        client.post(f"/api/v1/live-rooms/{room['id']}/start", headers=_auth(admin_token))
        _recv_until(ws, ServerEventType.QUESTION_STARTED)

        # Question timeLimitSeconds=2 → auto close → reveal → next.
        closed = _recv_until(ws, ServerEventType.QUESTION_CLOSED)
        assert closed["payload"]["question"]["state"] == "Closed"
        reveal = _recv_until(ws, ServerEventType.QUESTION_REVEAL)
        assert reveal["payload"]["question"]["state"] in {"Revealed", "Scored"}
        next_q = _recv_until(ws, ServerEventType.QUESTION_STARTED)
        assert next_q["payload"]["question"]["promptText"] == "Q2?"
        auto_progression.cancel_room(UUID(room["id"]))
