"""Integration tests for Quiz Execution Engine (manual progression)."""

from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.websocket.events import ServerEventType
from app.core.exceptions import ValidationError
from app.models.enums import QuizStatus, RoomState, SessionQuestionState
from app.models.quiz import Quiz
from app.services.quiz_execution_service import QuizExecutionService


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _add_question(
    client: TestClient,
    token: str,
    quiz_id: str,
    section_id: str,
    prompt: str,
) -> str:
    question = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections/{section_id}/questions",
        headers=_auth(token),
        json={"questionType": "Text", "promptText": prompt},
    )
    assert question.status_code == 201, question.text
    q_id = question.json()["data"]["id"]
    for text, correct, order in (("Yes", True, 0), ("No", False, 1)):
        opt = client.post(
            f"/api/v1/quizzes/{quiz_id}/sections/{section_id}/questions/{q_id}/options",
            headers=_auth(token),
            json={"text": text, "isCorrect": correct, "sortOrder": order},
        )
        assert opt.status_code == 201, opt.text
    return q_id


def _build_multi_section_quiz(
    client: TestClient,
    token: str,
    db: Session,
    *,
    title: str,
) -> str:
    """Two sections: A has 2 questions, B has 1 question."""
    quiz = client.post(
        "/api/v1/quizzes",
        headers=_auth(token),
        json={"title": title},
    )
    assert quiz.status_code == 201
    quiz_id = quiz.json()["data"]["id"]

    sec_a = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections",
        headers=_auth(token),
        json={"name": "Section A"},
    ).json()["data"]["id"]
    sec_b = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections",
        headers=_auth(token),
        json={"name": "Section B"},
    ).json()["data"]["id"]

    _add_question(client, token, quiz_id, sec_a, "A1?")
    _add_question(client, token, quiz_id, sec_a, "A2?")
    _add_question(client, token, quiz_id, sec_b, "B1?")

    row = db.get(Quiz, UUID(quiz_id))
    assert row is not None
    row.status = QuizStatus.READY
    db.commit()
    return quiz_id


def _active_room(
    client: TestClient,
    token: str,
    db: Session,
    *,
    title: str,
) -> dict:
    quiz_id = _build_multi_section_quiz(client, token, db, title=title)
    room = client.post(
        "/api/v1/live-rooms",
        headers=_auth(token),
        json={"quizId": quiz_id},
    ).json()["data"]
    client.post(f"/api/v1/live-rooms/{room['id']}/open-lobby", headers=_auth(token))
    started = client.post(
        f"/api/v1/live-rooms/{room['id']}/start",
        headers=_auth(token),
    )
    assert started.status_code == 200, started.text
    return started.json()["data"]


def _recv_until(ws, event_type: str, *, limit: int = 20) -> dict:
    for _ in range(limit):
        msg = ws.receive_json()
        if msg.get("type") == event_type:
            return msg
    raise AssertionError(f"Did not receive event type {event_type}")


def _lifecycle_to_reveal(svc: QuizExecutionService, room_id: UUID) -> None:
    svc.start_first_question(room_id)
    svc.close_question(room_id)
    svc.reveal_answer(room_id)


def test_start_quiz_broadcasts_first_question(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room = _active_room(client, admin_token, db_session, title="Exec Start")
    room_id = UUID(room["id"])

    with client.websocket_connect(
        f"/ws?role=admin&token={admin_token}&roomId={room['id']}",
    ) as ws:
        _recv_until(ws, ServerEventType.CONNECTION_ACK)
        _recv_until(ws, ServerEventType.RESYNC)

        ws.send_json({"type": "admin:start_question", "payload": {}})
        section = _recv_until(ws, ServerEventType.SECTION_STARTED)
        assert section["payload"]["section"]["name"] == "Section A"
        started = _recv_until(ws, ServerEventType.QUESTION_STARTED)
        assert started["payload"]["questionIndex"] == 0
        assert started["payload"]["question"]["promptText"] == "A1?"
        assert started["payload"]["question"]["state"] == "Open"
        opts = started["payload"]["question"]["options"]
        assert all("isCorrect" not in o for o in opts)

    # WS commits on a separate SQLAlchemy session — refresh local identity map.
    db_session.expire_all()
    svc = QuizExecutionService(db_session)
    refreshed = svc._require_room(room_id)
    assert refreshed.state == RoomState.ACTIVE
    assert refreshed.current_question_index == 0
    q0 = sorted(refreshed.session_questions, key=lambda q: q.sort_order)[0]
    assert q0.state == SessionQuestionState.OPEN


def test_next_question_within_section(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room = _active_room(client, admin_token, db_session, title="Exec Next Q")
    room_id = UUID(room["id"])
    svc = QuizExecutionService(db_session)

    _lifecycle_to_reveal(svc, room_id)
    result = svc.next_question(room_id)
    assert any(e.type == "question:started" for e in result.events)
    assert result.room.current_question_index == 1
    q = sorted(result.room.session_questions, key=lambda x: x.sort_order)[1]
    assert q.state == SessionQuestionState.OPEN


def test_end_of_section_and_next_section(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room = _active_room(client, admin_token, db_session, title="Exec Section")
    room_id = UUID(room["id"])
    svc = QuizExecutionService(db_session)

    _lifecycle_to_reveal(svc, room_id)
    svc.next_question(room_id)
    svc.close_question(room_id)
    svc.reveal_answer(room_id)
    break_result = svc.next_question(room_id)
    assert break_result.room.state == RoomState.SECTION_BREAK
    assert any(e.type == "section:break" for e in break_result.events)
    assert not any(e.type == "question:started" for e in break_result.events)

    continued = svc.next_section(room_id)
    assert continued.room.state == RoomState.ACTIVE
    assert continued.room.current_question_index == 2
    types = [e.type for e in continued.events]
    assert "section:continued" in types
    assert "section:started" in types
    assert "question:started" in types
    started = next(e for e in continued.events if e.type == "question:started")
    assert started.payload["question"]["promptText"] == "B1?"


def test_final_question_completes_quiz(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room = _active_room(client, admin_token, db_session, title="Exec Complete")
    room_id = UUID(room["id"])
    svc = QuizExecutionService(db_session)

    _lifecycle_to_reveal(svc, room_id)
    svc.next_question(room_id)
    svc.close_question(room_id)
    svc.reveal_answer(room_id)
    svc.next_question(room_id)
    svc.next_section(room_id)
    svc.close_question(room_id)
    svc.reveal_answer(room_id)
    done = svc.next_question(room_id)

    assert done.room.state == RoomState.COMPLETED
    assert done.room.completed_at is not None
    assert any(e.type == "quiz:completed" for e in done.events)
    assert any(e.type == "room:completed" for e in done.events)


def test_invalid_transitions(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room = _active_room(client, admin_token, db_session, title="Exec Invalid")
    room_id = UUID(room["id"])
    svc = QuizExecutionService(db_session)
    db_session.expire_all()

    # Start Quiz opens the first question automatically.
    again = svc.start_first_question(room_id)
    assert any(e.type == "question:started" for e in again.events)

    try:
        svc.next_question(room_id)
        raise AssertionError("expected ValidationError")
    except ValidationError as exc:
        assert exc.code == "QUESTION_STILL_OPEN"

    svc.close_question(room_id)

    try:
        svc.next_question(room_id)
        raise AssertionError("expected ValidationError")
    except ValidationError as exc:
        assert exc.code == "REVEAL_REQUIRED"

    try:
        svc.next_section(room_id)
        raise AssertionError("expected ValidationError")
    except ValidationError as exc:
        assert exc.code == "INVALID_STATE_TRANSITION"


def test_double_reveal(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room = _active_room(client, admin_token, db_session, title="Exec Double Reveal")
    room_id = UUID(room["id"])
    svc = QuizExecutionService(db_session)

    svc.start_first_question(room_id)
    svc.close_question(room_id)
    result = svc.reveal_answer(room_id)
    reveal = next(e for e in result.events if e.type == "question:reveal")
    assert any(o.get("isCorrect") is True for o in reveal.payload["question"]["options"])
    assert any(e.type == "question:scored" for e in result.events)

    # Repeated reveal is idempotent (scoring must not change totals again).
    again = svc.reveal_answer(room_id)
    assert any(e.type == "question:reveal" for e in again.events)
    assert any(e.type == "question:scored" for e in again.events)


def test_advance_past_end(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room = _active_room(client, admin_token, db_session, title="Exec Past End")
    room_id = UUID(room["id"])
    svc = QuizExecutionService(db_session)

    _lifecycle_to_reveal(svc, room_id)
    svc.next_question(room_id)
    svc.close_question(room_id)
    svc.reveal_answer(room_id)
    svc.next_question(room_id)
    svc.next_section(room_id)
    svc.close_question(room_id)
    svc.reveal_answer(room_id)
    svc.next_question(room_id)

    try:
        svc.next_question(room_id)
        raise AssertionError("expected ValidationError")
    except ValidationError as exc:
        assert exc.code == "QUIZ_ALREADY_COMPLETED"

    try:
        svc.start_first_question(room_id)
        raise AssertionError("expected ValidationError")
    except ValidationError as exc:
        assert exc.code == "QUIZ_ALREADY_COMPLETED"

    try:
        svc.end_quiz(room_id)
        raise AssertionError("expected ValidationError")
    except ValidationError as exc:
        assert exc.code == "QUIZ_ALREADY_COMPLETED"


def test_end_quiz_mid_session(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room = _active_room(client, admin_token, db_session, title="Exec End Mid")
    room_id = UUID(room["id"])
    svc = QuizExecutionService(db_session)
    svc.start_first_question(room_id)
    result = svc.end_quiz(room_id)
    assert result.room.state == RoomState.COMPLETED
    assert result.room.completed_at is not None
    assert any(e.type == "quiz:completed" for e in result.events)


def test_ws_full_progression_broadcasts(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room = _active_room(client, admin_token, db_session, title="Exec WS Flow")

    with client.websocket_connect(
        f"/ws?role=admin&token={admin_token}&roomId={room['id']}",
    ) as ws:
        _recv_until(ws, ServerEventType.CONNECTION_ACK)
        _recv_until(ws, ServerEventType.RESYNC)

        def send_and_expect(event: str, *expected: str) -> list[dict]:
            ws.send_json({"type": event, "payload": {}})
            return [_recv_until(ws, t) for t in expected]

        send_and_expect(
            "admin:start_question",
            ServerEventType.SECTION_STARTED,
            ServerEventType.QUESTION_STARTED,
        )
        send_and_expect("admin:close_question", ServerEventType.QUESTION_CLOSED)
        reveal = send_and_expect("admin:reveal_answer", ServerEventType.QUESTION_REVEAL)[0]
        assert "isCorrect" in reveal["payload"]["question"]["options"][0]

        send_and_expect("admin:next_question", ServerEventType.QUESTION_STARTED)
        send_and_expect("admin:close_question", ServerEventType.QUESTION_CLOSED)
        send_and_expect("admin:reveal_answer", ServerEventType.QUESTION_REVEAL)

        send_and_expect(
            "admin:next_question",
            ServerEventType.SECTION_BREAK,
            ServerEventType.ROOM_STATE_CHANGED,
        )
        msgs = send_and_expect(
            "admin:next_section",
            ServerEventType.SECTION_CONTINUED,
            ServerEventType.SECTION_STARTED,
            ServerEventType.QUESTION_STARTED,
            ServerEventType.ROOM_STATE_CHANGED,
        )
        assert msgs[2]["payload"]["question"]["promptText"] == "B1?"

    db_session.expire_all()
    svc = QuizExecutionService(db_session)
    room_row = svc._require_room(UUID(room["id"]))
    assert room_row.state == RoomState.ACTIVE
    assert room_row.current_question_index == 2
