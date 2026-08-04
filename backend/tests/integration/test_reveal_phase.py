"""Reveal → leaderboard → next must stay synchronized across all client roles."""

from __future__ import annotations

import time
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.websocket.events import ServerEventType
from app.models.enums import QuizStatus
from app.models.quiz import Quiz
from app.services.timer_service import auto_progression


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _ready_quiz(
    client: TestClient,
    token: str,
    db: Session,
    title: str,
    *,
    time_limit_seconds: int = 30,
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
                "timeLimitSeconds": time_limit_seconds,
                "sortOrder": idx,
            },
        ).json()["data"]
        for text, correct, order in (
            ("Yes", True, 0),
            ("No", False, 1),
            ("Maybe", False, 2),
            ("Never", False, 3),
        ):
            client.post(
                f"/api/v1/quizzes/{quiz['id']}/sections/{section['id']}/questions/{q['id']}/options",
                headers=_auth(token),
                json={"text": text, "isCorrect": correct, "sortOrder": order},
            )
    assert (
        client.post(
            f"/api/v1/quizzes/{quiz['id']}/validate",
            headers=_auth(token),
        ).status_code
        == 200
    )
    row = db.get(Quiz, UUID(quiz["id"]))
    assert row is not None and row.status == QuizStatus.READY
    return quiz["id"]


def _recv_until(ws, event_type: str, *, limit: int = 80) -> dict:
    for _ in range(limit):
        msg = ws.receive_json()
        if msg.get("type") == event_type:
            return msg
    raise AssertionError(f"Did not receive {event_type}")


def _recv_until_any(ws, event_types: set[str], *, limit: int = 80) -> dict:
    for _ in range(limit):
        msg = ws.receive_json()
        if msg.get("type") in event_types:
            return msg
    raise AssertionError(f"Did not receive any of {event_types}")


def test_reveal_then_leaderboard_then_next_across_roles(
    client: TestClient,
    admin_token: str,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All answers → question:reveal (with isCorrect) → later leaderboard → next.

    Leaderboard must not arrive in the same batch as reveal so clients can show
    the Answer Reveal screen.
    """
    monkeypatch.setattr("app.services.timer_service.REVEAL_DWELL_SECONDS", 0.2)
    monkeypatch.setattr("app.services.timer_service.LEADERBOARD_DWELL_SECONDS", 0.2)

    quiz_id = _ready_quiz(client, admin_token, db_session, "Reveal Phase Sync")
    room = client.post(
        "/api/v1/live-rooms",
        headers=_auth(admin_token),
        json={"quizId": quiz_id, "config": {"questionAdvanceMode": "automatic"}},
    ).json()["data"]
    room_id = room["id"]
    secret = room["secretToken"]

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
            "displayName": "Revealer",
            "email": "reveal-phase@example.com",
        },
    )
    assert join.status_code == 201, join.text
    session_token = join.json()["data"]["sessionToken"]

    with client.websocket_connect(
        f"/ws?role=admin&token={admin_token}&roomId={room_id}",
    ) as admin_ws, client.websocket_connect(
        f"/ws?role=participant&token={session_token}",
    ) as pws, client.websocket_connect(
        f"/ws?role=display&token={secret}",
    ) as dws:
        for ws in (admin_ws, pws, dws):
            _recv_until(ws, ServerEventType.CONNECTION_ACK)
            _recv_until(ws, ServerEventType.RESYNC)

        assert (
            client.post(
                f"/api/v1/live-rooms/{room_id}/start",
                headers=_auth(admin_token),
            ).status_code
            == 200
        )

        q1 = _recv_until(pws, ServerEventType.QUESTION_STARTED)
        _recv_until(dws, ServerEventType.QUESTION_STARTED)
        _recv_until(admin_ws, ServerEventType.QUESTION_STARTED)
        opt_yes = next(
            o for o in q1["payload"]["question"]["options"] if o["text"] == "Yes"
        )

        # Submit the correct answer — all-answered triggers close→reveal pipeline.
        pws.send_json(
            {"type": "answer:submit", "payload": {"optionIds": [opt_yes["id"]]}},
        )
        _recv_until(pws, ServerEventType.ANSWER_ACCEPTED)

        reveal_p = _recv_until(pws, ServerEventType.QUESTION_REVEAL)
        reveal_d = _recv_until(dws, ServerEventType.QUESTION_REVEAL)
        reveal_a = _recv_until(admin_ws, ServerEventType.QUESTION_REVEAL)

        for reveal in (reveal_p, reveal_d, reveal_a):
            options = reveal["payload"]["question"]["options"]
            assert any(o.get("isCorrect") is True for o in options)
            assert reveal["payload"]["question"]["state"] in {"Revealed", "Scored"}

        # Correct option must be marked; participant also gets personal score.
        personal = _recv_until(pws, "score:personal")
        assert personal["payload"]["isCorrect"] is True

        # leaderboard:updated must NOT have arrived yet on the display socket —
        # drain nothing for a short window by checking timestamp separation.
        # Collect next events on display: should be leaderboard then Q2 started.
        t0 = time.monotonic()
        next_d = _recv_until_any(
            dws,
            {ServerEventType.LEADERBOARD_UPDATED, ServerEventType.QUESTION_STARTED},
        )
        elapsed = time.monotonic() - t0
        assert next_d["type"] == ServerEventType.LEADERBOARD_UPDATED, next_d
        # Reveal dwell (~0.2s) should have elapsed before standings.
        assert elapsed >= 0.12, f"leaderboard arrived too early: {elapsed:.3f}s"

        lb_p = _recv_until(pws, ServerEventType.LEADERBOARD_UPDATED)
        lb_a = _recv_until(admin_ws, ServerEventType.LEADERBOARD_UPDATED)
        assert lb_p["payload"].get("entries") or lb_p["payload"].get("leaderboard")
        assert lb_a["payload"].get("entries") or lb_a["payload"].get("leaderboard")

        t1 = time.monotonic()
        q2_d = _recv_until(dws, ServerEventType.QUESTION_STARTED)
        assert time.monotonic() - t1 >= 0.12, "next question arrived before leaderboard dwell"
        assert q2_d["payload"]["question"]["promptText"] == "Q2?"

        q2_p = _recv_until(pws, ServerEventType.QUESTION_STARTED)
        assert q2_p["payload"]["question"]["promptText"] == "Q2?"

    auto_progression.cancel_room(UUID(room_id))


def test_reveal_answer_events_omit_leaderboard(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    """Service-level: reveal_answer must not include leaderboard:updated."""
    from app.services.quiz_execution_service import QuizExecutionService

    quiz_id = _ready_quiz(client, admin_token, db_session, "Reveal Omits LB")
    room = client.post(
        "/api/v1/live-rooms",
        headers=_auth(admin_token),
        json={"quizId": quiz_id},
    ).json()["data"]
    room_id = UUID(room["id"])
    client.post(f"/api/v1/live-rooms/{room['id']}/open-lobby", headers=_auth(admin_token))
    client.post(
        "/api/v1/join",
        json={
            "roomCode": room["roomCode"],
            "displayName": "A",
            "email": "reveal-omit-lb@example.com",
        },
    )
    client.post(f"/api/v1/live-rooms/{room['id']}/start", headers=_auth(admin_token))

    auto_progression.cancel_room(room_id)
    svc = QuizExecutionService(db_session)
    svc.close_question(room_id)
    result = svc.reveal_answer(room_id)
    types = [e.type for e in result.events]
    assert "question:reveal" in types
    assert "leaderboard:updated" not in types
    assert any(o.get("isCorrect") is True for o in result.events[0].payload["question"]["options"])
