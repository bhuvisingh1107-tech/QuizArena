"""Security: participants must not learn answers before question:reveal."""

from __future__ import annotations

import json
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.websocket.events import ServerEventType
from app.core.crypto import is_sealed
from app.models.enums import QuizStatus
from app.models.question import Question
from app.models.quiz import Quiz
from app.repositories.answer_option_repository import AnswerOptionRepository
from app.services.leaderboard_service import LeaderboardService
from app.services.quiz_execution_service import QuizExecutionService
from app.services.response_service import FORBIDDEN_PRE_REVEAL_KEYS, ResponseService
from app.services.scoring_service import ScoringService


FORBIDDEN_SUBSTRINGS = (
    "isCorrect",
    "correctOption",
    "correctAnswer",
    "answerIndex",
    "answerHash",
    "explanation",
    "pointsEarned",
    "lastIsCorrect",
    "totalCorrect",
    "totalIncorrect",
)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _recv_until(ws, event_type: str, *, limit: int = 40) -> dict:
    for _ in range(limit):
        msg = ws.receive_json()
        if msg.get("type") == event_type:
            return msg
    raise AssertionError(f"Did not receive {event_type}")


def _assert_no_forbidden(payload: object, *, allow: set[str] | None = None) -> None:
    allow = allow or set()
    raw = json.dumps(payload)

    def walk(node: object, path: str = "") -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in FORBIDDEN_PRE_REVEAL_KEYS and key not in allow:
                    raise AssertionError(f"Forbidden key {key!r} at {path}.{key}")
                for needle in FORBIDDEN_SUBSTRINGS:
                    if needle.lower() in key.lower() and key not in allow:
                        # explanation/isCorrect etc.
                        if key in allow:
                            continue
                        raise AssertionError(f"Forbidden key pattern {key!r} at {path}")
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for i, item in enumerate(node):
                walk(item, f"{path}[{i}]")

    walk(payload)
    for needle in ("data:image", "base64,"):
        assert needle not in raw.lower()


def _setup_room_with_encrypted_question(
    client: TestClient,
    token: str,
    db: Session,
    *,
    title: str,
) -> tuple[dict, list[str], dict]:
    quiz = client.post(
        "/api/v1/quizzes",
        headers=_auth(token),
        json={"title": title},
    ).json()["data"]
    quiz_id = quiz["id"]
    section_id = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections",
        headers=_auth(token),
        json={"name": "Security Round"},
    ).json()["data"]["id"]
    question = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections/{section_id}/questions",
        headers=_auth(token),
        json={
            "questionType": "Text",
            "promptText": "Capital of France?",
            "explanation": "Paris is the capital city of France.",
            "basePoints": 10,
        },
    ).json()["data"]
    qid = question["id"]
    for text, correct, order in (("Paris", True, 0), ("Lyon", False, 1)):
        opt = client.post(
            f"/api/v1/quizzes/{quiz_id}/sections/{section_id}/questions/{qid}/options",
            headers=_auth(token),
            json={"text": text, "isCorrect": correct, "sortOrder": order},
        )
        assert opt.status_code == 201, opt.text

    row = db.get(Quiz, UUID(quiz_id))
    assert row is not None
    row.status = QuizStatus.READY
    db.commit()

    room = client.post(
        "/api/v1/live-rooms",
        headers=_auth(token),
        json={"quizId": quiz_id},
    ).json()["data"]
    client.post(f"/api/v1/live-rooms/{room['id']}/open-lobby", headers=_auth(token))
    joined = client.post(
        "/api/v1/join",
        json={
            "roomCode": room["roomCode"],
            "displayName": "Pat",
            "email": f"pat-{title.lower().replace(' ', '')}@example.com",
        },
    ).json()["data"]
    started = client.post(
        f"/api/v1/live-rooms/{room['id']}/start",
        headers=_auth(token),
    )
    assert started.status_code == 200, started.text
    room_data = started.json()["data"]

    # Session snapshot assigns new option UUIDs — use those for submit.
    opened = QuizExecutionService(db).start_first_question(UUID(room_data["id"]))
    session_q = sorted(opened.room.session_questions, key=lambda q: q.sort_order)[0]
    option_ids = [str(o.id) for o in sorted(session_q.options, key=lambda o: o.sort_order)]
    return room_data, option_ids, joined


def test_authoring_tables_store_encrypted_fields(
    client: TestClient,
    admin_token: str,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.config import get_settings

    monkeypatch.setenv("QUESTION_ENCRYPTION_KEY", "security-audit-test-key-32bytes!!")
    get_settings.cache_clear()

    quiz = client.post(
        "/api/v1/quizzes",
        headers=_auth(admin_token),
        json={"title": "Encrypted At Rest"},
    ).json()["data"]
    section_id = client.post(
        f"/api/v1/quizzes/{quiz['id']}/sections",
        headers=_auth(admin_token),
        json={"name": "R1"},
    ).json()["data"]["id"]
    question = client.post(
        f"/api/v1/quizzes/{quiz['id']}/sections/{section_id}/questions",
        headers=_auth(admin_token),
        json={
            "questionType": "Text",
            "promptText": "What is 2+2?",
            "explanation": "Basic arithmetic: two plus two equals four.",
        },
    ).json()["data"]
    opt = client.post(
        f"/api/v1/quizzes/{quiz['id']}/sections/{section_id}/questions/{question['id']}/options",
        headers=_auth(admin_token),
        json={"text": "Four", "isCorrect": True, "sortOrder": 0},
    )
    assert opt.status_code == 201, opt.text

    db_session.expire_all()
    qrow = db_session.get(Question, UUID(question["id"]))
    assert qrow is not None
    assert is_sealed(qrow.prompt_text or "")
    assert is_sealed(qrow.explanation or "")

    options = AnswerOptionRepository(db_session).list_for_question(UUID(question["id"]))
    assert options
    assert is_sealed(options[0].text)
    assert options[0].is_correct is False  # decoy column


def test_question_started_has_no_answer_fields(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room, _option_ids, joined = _setup_room_with_encrypted_question(
        client, admin_token, db_session, title="Sec Start"
    )

    with client.websocket_connect(
        f"/ws?role=participant&token={joined['sessionToken']}",
    ) as ws:
        _recv_until(ws, ServerEventType.CONNECTION_ACK)
        _recv_until(ws, ServerEventType.RESYNC)

        with client.websocket_connect(
            f"/ws?role=admin&token={admin_token}&roomId={room['id']}",
        ) as admin_ws:
            _recv_until(admin_ws, ServerEventType.CONNECTION_ACK)
            _recv_until(admin_ws, ServerEventType.RESYNC)
            admin_ws.send_json({"type": "admin:start_question", "payload": {}})

        started = _recv_until(ws, ServerEventType.QUESTION_STARTED)

    question = started["payload"]["question"]
    assert "explanation" not in question
    for opt in question["options"]:
        assert "isCorrect" not in opt
    _assert_no_forbidden(started["payload"])


def test_answer_accepted_and_me_leak_no_correctness(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room, option_ids, joined = _setup_room_with_encrypted_question(
        client, admin_token, db_session, title="Sec Submit"
    )
    room_id = UUID(room["id"])
    # Question already opened by setup helper.

    me_before = client.get(
        "/api/v1/participants/me",
        headers=_auth(joined["sessionToken"]),
    ).json()["data"]["participant"]
    assert me_before["totalScore"] == 0
    assert me_before["totalCorrect"] == 0

    result = ResponseService(db_session).submit(
        room_id=room_id,
        participant_id=UUID(joined["participant"]["id"]),
        option_ids=[UUID(option_ids[0])],
        require_connected=False,
    )
    accept = next(e for e in result.events if e.type == "answer:accepted")
    assert accept.payload["status"] == "submitted"
    assert set(accept.payload.keys()) <= {
        "roomId",
        "questionId",
        "questionIndex",
        "responseId",
        "selectedOptionIds",
        "submittedAt",
        "responseTimeMs",
        "status",
    }
    _assert_no_forbidden(accept.payload)
    assert not any(e.type == "leaderboard:updated" for e in result.events)

    me_after = client.get(
        "/api/v1/participants/me",
        headers=_auth(joined["sessionToken"]),
    ).json()["data"]["participant"]
    assert me_after["totalScore"] == me_before["totalScore"]
    assert me_after["totalCorrect"] == 0
    assert me_after["totalIncorrect"] == 0
    assert me_after["streak"] == me_before["streak"]

    board = LeaderboardService(db_session).snapshot(room_id)
    assert all("lastIsCorrect" not in e for e in board["entries"])

    status = ResponseService(db_session).get_submission_status(
        room_id=room_id,
        participant_id=UUID(joined["participant"]["id"]),
    )
    assert status["hasSubmitted"] is True
    assert status["status"] == "submitted"


def test_correctness_only_on_reveal(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room, option_ids, joined = _setup_room_with_encrypted_question(
        client, admin_token, db_session, title="Sec Reveal"
    )
    room_id = UUID(room["id"])
    exec_svc = QuizExecutionService(db_session)
    exec_svc.start_first_question(room_id)
    ResponseService(db_session).submit(
        room_id=room_id,
        participant_id=UUID(joined["participant"]["id"]),
        option_ids=[UUID(option_ids[0])],
        require_connected=False,
    )
    exec_svc.close_question(room_id)
    result = exec_svc.reveal_answer(room_id)

    reveal = next(e for e in result.events if e.type == "question:reveal")
    question = reveal.payload["question"]
    assert any(o.get("isCorrect") is True for o in question["options"])
    assert "explanation" in question

    personal = next(e for e in result.events if e.type == "score:personal")
    assert personal.payload["isCorrect"] is True
    assert personal.payload["pointsEarned"] > 0

    db_session.expire_all()
    board = LeaderboardService(db_session).snapshot(room_id)
    assert any(e.get("lastIsCorrect") is True for e in board["entries"])


def test_manipulating_option_ids_cannot_force_correctness(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room, option_ids, joined = _setup_room_with_encrypted_question(
        client, admin_token, db_session, title="Sec Force"
    )
    room_id = UUID(room["id"])
    # Question already opened by setup helper.
    # Submit wrong answer
    ResponseService(db_session).submit(
        room_id=room_id,
        participant_id=UUID(joined["participant"]["id"]),
        option_ids=[UUID(option_ids[1])],
        require_connected=False,
    )
    QuizExecutionService(db_session).close_question(room_id)
    QuizExecutionService(db_session).reveal_answer(room_id)

    summary = ScoringService(db_session).score_question(room_id, include_leaderboard=False)
    assert summary.incorrect_count == 1
    assert summary.correct_count == 0
