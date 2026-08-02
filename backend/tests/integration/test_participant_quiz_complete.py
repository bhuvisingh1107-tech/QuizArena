"""Participant must receive quiz:completed when the final question advances."""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.websocket.events import ServerEventType
from app.models.enums import QuizStatus, RoomState
from app.models.quiz import Quiz
from app.services.quiz_execution_service import QuizExecutionService
from app.services.timer_service import AutoProgressionScheduler, auto_progression


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _ready_quiz_two_questions(
    client: TestClient,
    token: str,
    db: Session,
    title: str,
) -> str:
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
    for idx, prompt in enumerate(("Q1?", "Q2?")):
        q = client.post(
            f"/api/v1/quizzes/{quiz['id']}/sections/{section['id']}/questions",
            headers=_auth(token),
            json={
                "questionType": "Text",
                "promptText": prompt,
                "timeLimitSeconds": 30,
                "sortOrder": idx,
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


def _recv_until(ws, event_type: str, *, limit: int = 80) -> dict:
    for _ in range(limit):
        msg = ws.receive_json()
        if msg.get("type") == event_type:
            return msg
    raise AssertionError(f"Did not receive {event_type}")


def test_final_next_question_broadcasts_quiz_completed_to_participant(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    """Host advances past the last question → participant gets quiz:completed + podium."""
    quiz_id = _ready_quiz_two_questions(
        client, admin_token, db_session, "Complete Without Refresh"
    )
    room = client.post(
        "/api/v1/live-rooms",
        headers=_auth(admin_token),
        json={"quizId": quiz_id},
    ).json()["data"]
    room_id = room["id"]

    assert (
        client.post(
            f"/api/v1/live-rooms/{room_id}/open-lobby",
            headers=_auth(admin_token),
        ).status_code
        == 200
    )

    join = client.post(
        "/api/v1/join",
        json={
            "roomCode": room["roomCode"],
            "displayName": "Finisher",
            "email": "finisher-complete@example.com",
        },
    )
    assert join.status_code == 201, join.text
    session_token = join.json()["data"]["sessionToken"]

    with client.websocket_connect(
        f"/ws?role=admin&token={admin_token}&roomId={room_id}",
    ) as admin_ws, client.websocket_connect(
        f"/ws?role=participant&token={session_token}",
    ) as pws:
        _recv_until(admin_ws, ServerEventType.CONNECTION_ACK)
        _recv_until(admin_ws, ServerEventType.RESYNC)
        _recv_until(pws, ServerEventType.CONNECTION_ACK)
        _recv_until(pws, ServerEventType.RESYNC)

        started = client.post(
            f"/api/v1/live-rooms/{room_id}/start",
            headers=_auth(admin_token),
        )
        assert started.status_code == 200

        q1 = _recv_until(pws, ServerEventType.QUESTION_STARTED)
        opt1 = q1["payload"]["question"]["options"][0]["id"]
        pws.send_json({"type": "answer:submit", "payload": {"optionIds": [opt1]}})
        _recv_until(pws, ServerEventType.ANSWER_ACCEPTED)

        def admin_step(command: str, *expected: str) -> None:
            auto_progression.cancel_room(UUID(room_id))
            admin_ws.send_json({"type": command, "payload": {}})
            for event_type in expected:
                _recv_until(admin_ws, event_type)

        admin_step("admin:close_question", ServerEventType.QUESTION_CLOSED)
        admin_step("admin:reveal_answer", ServerEventType.QUESTION_REVEAL)
        admin_step("admin:next_question", ServerEventType.QUESTION_STARTED)

        q2 = _recv_until(pws, ServerEventType.QUESTION_STARTED)
        opt2 = q2["payload"]["question"]["options"][0]["id"]
        pws.send_json({"type": "answer:submit", "payload": {"optionIds": [opt2]}})
        _recv_until(pws, ServerEventType.ANSWER_ACCEPTED)

        admin_step("admin:close_question", ServerEventType.QUESTION_CLOSED)
        admin_step("admin:reveal_answer", ServerEventType.QUESTION_REVEAL)

        # Final advance → Completed. Participant must get quiz:completed live
        # (no page refresh) with podium/standings in the payload.
        auto_progression.cancel_room(UUID(room_id))
        admin_ws.send_json({"type": "admin:next_question", "payload": {}})
        completed = _recv_until(pws, ServerEventType.QUIZ_COMPLETED)
        assert completed["payload"]["state"] == "Completed"
        podium = completed["payload"].get("podium")
        assert podium is not None
        entries = podium.get("entries") if isinstance(podium, dict) else podium
        assert entries

        db_session.expire_all()
        row = QuizExecutionService(db_session).get_execution_state(UUID(room_id)).room
        assert row.state == RoomState.COMPLETED

    auto_progression.cancel_room(UUID(room_id))


def test_cancel_room_does_not_cancel_running_pipeline_task() -> None:
    """Regression: cancel from inside the room task must not abort the pipeline."""
    scheduler = AutoProgressionScheduler()
    room_id = uuid4()
    finished = False

    async def pipeline() -> None:
        nonlocal finished
        scheduler._tasks[room_id] = asyncio.current_task()  # type: ignore[assignment]
        scheduler.cancel_room(room_id)
        await asyncio.sleep(0)
        finished = True

    asyncio.run(pipeline())
    assert finished is True


def test_complete_quiz_emits_events_without_cancelling_auto_progression(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    """_complete_quiz must return quiz:completed events (broadcast is caller's job)."""
    quiz_id = _ready_quiz_two_questions(
        client, admin_token, db_session, "Complete Emits Events"
    )
    room = client.post(
        "/api/v1/live-rooms",
        headers=_auth(admin_token),
        json={"quizId": quiz_id},
    ).json()["data"]
    room_id = UUID(room["id"])

    assert (
        client.post(
            f"/api/v1/live-rooms/{room['id']}/open-lobby",
            headers=_auth(admin_token),
        ).status_code
        == 200
    )
    client.post(
        "/api/v1/join",
        json={
            "roomCode": room["roomCode"],
            "displayName": "X",
            "email": "complete-events@example.com",
        },
    )
    assert (
        client.post(
            f"/api/v1/live-rooms/{room['id']}/start",
            headers=_auth(admin_token),
        ).status_code
        == 200
    )

    auto_progression.cancel_room(room_id)
    svc = QuizExecutionService(db_session)
    svc.close_question(room_id)
    svc.reveal_answer(room_id)
    svc.next_question(room_id)
    svc.close_question(room_id)
    svc.reveal_answer(room_id)
    done = svc.next_question(room_id)
    assert done.room.state == RoomState.COMPLETED
    assert any(e.type == "quiz:completed" for e in done.events)
    assert any(e.type == "room:completed" for e in done.events)
    assert any(e.type == "leaderboard:updated" for e in done.events)
