"""Integration tests for Scoring Engine (PROJECT_SPEC.md §12)."""

from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.websocket.events import ServerEventType
from app.models.enums import QuizStatus, SessionQuestionState
from app.models.participant import Participant
from app.models.quiz import Quiz
from app.models.response import Response
from app.services.quiz_execution_service import QuizExecutionService
from app.services.response_service import ResponseService
from app.services.scoring_service import ScoringService


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _ready_quiz(
    client: TestClient,
    token: str,
    db: Session,
    *,
    title: str,
    allow_multiple: bool = False,
) -> str:
    quiz_id = client.post(
        "/api/v1/quizzes",
        headers=_auth(token),
        json={"title": title},
    ).json()["data"]["id"]
    section_id = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections",
        headers=_auth(token),
        json={"name": "R1"},
    ).json()["data"]["id"]
    q = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections/{section_id}/questions",
        headers=_auth(token),
        json={
            "questionType": "Text",
            "promptText": "Pick",
            "basePoints": 10,
            "allowMultipleCorrect": allow_multiple,
        },
    )
    assert q.status_code == 201, q.text
    q_id = q.json()["data"]["id"]
    if allow_multiple:
        options = (("A", True, 0), ("B", True, 1), ("C", False, 2))
    else:
        options = (("A", True, 0), ("B", False, 1))
    for text, correct, order in options:
        client.post(
            f"/api/v1/quizzes/{quiz_id}/sections/{section_id}/questions/{q_id}/options",
            headers=_auth(token),
            json={"text": text, "isCorrect": correct, "sortOrder": order},
        )
    row = db.get(Quiz, UUID(quiz_id))
    assert row is not None
    row.status = QuizStatus.READY
    db.commit()
    return quiz_id


def _join(client: TestClient, room_code: str, name: str, email: str) -> dict:
    response = client.post(
        "/api/v1/join",
        json={"roomCode": room_code, "displayName": name, "email": email},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _setup_open_question(
    client: TestClient,
    token: str,
    db: Session,
    *,
    title: str,
    joiners: list[tuple[str, str]],
    allow_multiple: bool = False,
) -> tuple[dict, list[str], list[dict]]:
    quiz_id = _ready_quiz(
        client, token, db, title=title, allow_multiple=allow_multiple
    )
    room = client.post(
        "/api/v1/live-rooms",
        headers=_auth(token),
        json={"quizId": quiz_id},
    ).json()["data"]
    client.post(f"/api/v1/live-rooms/{room['id']}/open-lobby", headers=_auth(token))
    joined = [_join(client, room["roomCode"], n, e) for n, e in joiners]
    client.post(f"/api/v1/live-rooms/{room['id']}/start", headers=_auth(token))
    exec_svc = QuizExecutionService(db)
    result = exec_svc.start_first_question(UUID(room["id"]))
    question = sorted(result.room.session_questions, key=lambda q: q.sort_order)[0]
    option_ids = [str(o.id) for o in sorted(question.options, key=lambda o: o.sort_order)]
    room = client.get(
        f"/api/v1/live-rooms/{room['id']}",
        headers=_auth(token),
    ).json()["data"]
    return room, option_ids, joined


def _close_and_reveal(db: Session, room_id: UUID):
    exec_svc = QuizExecutionService(db)
    exec_svc.close_question(room_id)
    return exec_svc.reveal_answer(room_id)


def _recv_until(ws, event_type: str, *, limit: int = 40) -> dict:
    for _ in range(limit):
        msg = ws.receive_json()
        if msg.get("type") == event_type:
            return msg
    raise AssertionError(f"Did not receive {event_type}")


def test_correct_answer(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room, option_ids, [joined] = _setup_open_question(
        client,
        admin_token,
        db_session,
        title="Score Correct",
        joiners=[("Ann", "ann@example.com")],
    )
    ResponseService(db_session).submit(
        room_id=UUID(room["id"]),
        participant_id=UUID(joined["participant"]["id"]),
        option_ids=[UUID(option_ids[0])],
        require_connected=False,
    )
    result = _close_and_reveal(db_session, UUID(room["id"]))
    assert any(e.type == "question:scored" for e in result.events)

    db_session.expire_all()
    response = db_session.scalars(select(Response)).one()
    assert response.is_correct is True
    assert response.is_unanswered is False
    assert response.base_points_earned == 10
    assert response.total_points_earned == 10
    assert response.scored_at is not None
    assert response.status == "correct"

    participant = db_session.get(Participant, UUID(joined["participant"]["id"]))
    assert participant is not None
    assert participant.total_score == 10
    assert participant.total_correct == 1
    assert participant.total_incorrect == 0
    assert participant.unanswered_count == 0
    assert participant.streak == 1


def test_incorrect_answer(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room, option_ids, [joined] = _setup_open_question(
        client,
        admin_token,
        db_session,
        title="Score Incorrect",
        joiners=[("Ben", "ben@example.com")],
    )
    ResponseService(db_session).submit(
        room_id=UUID(room["id"]),
        participant_id=UUID(joined["participant"]["id"]),
        option_ids=[UUID(option_ids[1])],
        require_connected=False,
    )
    _close_and_reveal(db_session, UUID(room["id"]))

    db_session.expire_all()
    response = db_session.scalars(select(Response)).one()
    assert response.is_correct is False
    assert response.total_points_earned == 0
    assert response.status == "incorrect"

    participant = db_session.get(Participant, UUID(joined["participant"]["id"]))
    assert participant is not None
    assert participant.total_score == 0
    assert participant.total_incorrect == 1
    assert participant.streak == 0


def test_unanswered_participant(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room, _option_ids, [joined] = _setup_open_question(
        client,
        admin_token,
        db_session,
        title="Score Unanswered",
        joiners=[("Cat", "cat@example.com")],
    )
    result = _close_and_reveal(db_session, UUID(room["id"]))
    scored = next(e for e in result.events if e.type == "question:scored")
    assert scored.payload["unansweredCount"] == 1
    assert scored.payload["totalSubmissions"] == 0

    db_session.expire_all()
    response = db_session.scalars(select(Response)).one()
    assert response.is_unanswered is True
    assert response.is_correct is False
    assert response.total_points_earned == 0
    assert response.status == "unanswered"

    participant = db_session.get(Participant, UUID(joined["participant"]["id"]))
    assert participant is not None
    assert participant.unanswered_count == 1
    assert participant.total_score == 0
    assert participant.streak == 0


def test_multiple_participants(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room, option_ids, [p1, p2, p3] = _setup_open_question(
        client,
        admin_token,
        db_session,
        title="Score Multi",
        joiners=[
            ("D1", "d1@example.com"),
            ("D2", "d2@example.com"),
            ("D3", "d3@example.com"),
        ],
    )
    svc = ResponseService(db_session)
    svc.submit(
        room_id=UUID(room["id"]),
        participant_id=UUID(p1["participant"]["id"]),
        option_ids=[UUID(option_ids[0])],
        require_connected=False,
    )
    svc.submit(
        room_id=UUID(room["id"]),
        participant_id=UUID(p2["participant"]["id"]),
        option_ids=[UUID(option_ids[1])],
        require_connected=False,
    )
    # p3 unanswered
    result = _close_and_reveal(db_session, UUID(room["id"]))
    scored = next(e for e in result.events if e.type == "question:scored")
    assert scored.payload["totalSubmissions"] == 2
    assert scored.payload["correctCount"] == 1
    assert scored.payload["incorrectCount"] == 1
    assert scored.payload["unansweredCount"] == 1
    assert "participantId" not in scored.payload


def test_multi_select_all_or_nothing(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room, option_ids, [full, partial] = _setup_open_question(
        client,
        admin_token,
        db_session,
        title="Score MultiSelect",
        joiners=[("E1", "e1@example.com"), ("E2", "e2@example.com")],
        allow_multiple=True,
    )
    svc = ResponseService(db_session)
    # Correct: A+B
    svc.submit(
        room_id=UUID(room["id"]),
        participant_id=UUID(full["participant"]["id"]),
        option_ids=[UUID(option_ids[0]), UUID(option_ids[1])],
        require_connected=False,
    )
    # Partial: only A → incorrect / zero points
    svc.submit(
        room_id=UUID(room["id"]),
        participant_id=UUID(partial["participant"]["id"]),
        option_ids=[UUID(option_ids[0])],
        require_connected=False,
    )
    _close_and_reveal(db_session, UUID(room["id"]))

    db_session.expire_all()
    full_p = db_session.get(Participant, UUID(full["participant"]["id"]))
    partial_p = db_session.get(Participant, UUID(partial["participant"]["id"]))
    assert full_p is not None and partial_p is not None
    assert full_p.total_score == 10
    assert full_p.total_correct == 1
    assert partial_p.total_score == 0
    assert partial_p.total_incorrect == 1


def test_duplicate_scoring_prevention_and_idempotency(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room, option_ids, [joined] = _setup_open_question(
        client,
        admin_token,
        db_session,
        title="Score Idempotent",
        joiners=[("Fay", "fay@example.com")],
    )
    ResponseService(db_session).submit(
        room_id=UUID(room["id"]),
        participant_id=UUID(joined["participant"]["id"]),
        option_ids=[UUID(option_ids[0])],
        require_connected=False,
    )
    _close_and_reveal(db_session, UUID(room["id"]))

    db_session.expire_all()
    before = db_session.get(Participant, UUID(joined["participant"]["id"]))
    assert before is not None
    score_before = before.total_score
    correct_before = before.total_correct

    # Direct re-score and repeated reveal must not change totals.
    summary = ScoringService(db_session).score_question(UUID(room["id"]))
    assert summary.already_scored is True

    QuizExecutionService(db_session).reveal_answer(UUID(room["id"]))

    db_session.expire_all()
    after = db_session.get(Participant, UUID(joined["participant"]["id"]))
    assert after is not None
    assert after.total_score == score_before
    assert after.total_correct == correct_before

    responses = list(db_session.scalars(select(Response)).all())
    assert len(responses) == 1
    assert responses[0].total_points_earned == 10


def test_participant_total_updates_across_questions(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    """Two-question quiz: verify cumulative totals and streak reset."""
    quiz_id = client.post(
        "/api/v1/quizzes",
        headers=_auth(admin_token),
        json={"title": "Score Two Q"},
    ).json()["data"]["id"]
    section_id = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections",
        headers=_auth(admin_token),
        json={"name": "R1"},
    ).json()["data"]["id"]

    option_sets: list[list[str]] = []
    for prompt in ("Q1", "Q2"):
        q_id = client.post(
            f"/api/v1/quizzes/{quiz_id}/sections/{section_id}/questions",
            headers=_auth(admin_token),
            json={"questionType": "Text", "promptText": prompt, "basePoints": 5},
        ).json()["data"]["id"]
        ids = []
        for text, correct, order in (("Yes", True, 0), ("No", False, 1)):
            opt = client.post(
                f"/api/v1/quizzes/{quiz_id}/sections/{section_id}/questions/{q_id}/options",
                headers=_auth(admin_token),
                json={"text": text, "isCorrect": correct, "sortOrder": order},
            ).json()["data"]["id"]
            ids.append(opt)
        option_sets.append(ids)

    row = db_session.get(Quiz, UUID(quiz_id))
    assert row is not None
    row.status = QuizStatus.READY
    db_session.commit()

    room = client.post(
        "/api/v1/live-rooms",
        headers=_auth(admin_token),
        json={"quizId": quiz_id},
    ).json()["data"]
    client.post(f"/api/v1/live-rooms/{room['id']}/open-lobby", headers=_auth(admin_token))
    joined = _join(client, room["roomCode"], "Gus", "gus@example.com")
    client.post(f"/api/v1/live-rooms/{room['id']}/start", headers=_auth(admin_token))

    room_id = UUID(room["id"])
    pid = UUID(joined["participant"]["id"])
    exec_svc = QuizExecutionService(db_session)
    resp_svc = ResponseService(db_session)

    exec_svc.start_first_question(room_id)
    # Map session option ids from execution state
    state = exec_svc.get_execution_state(room_id)
    assert state.question is not None
    q1_opts = [str(o.id) for o in sorted(state.question.options, key=lambda o: o.sort_order)]
    resp_svc.submit(
        room_id=room_id,
        participant_id=pid,
        option_ids=[UUID(q1_opts[0])],
        require_connected=False,
    )
    exec_svc.close_question(room_id)
    exec_svc.reveal_answer(room_id)

    db_session.expire_all()
    p = db_session.get(Participant, pid)
    assert p is not None
    assert p.total_score == 5
    assert p.streak == 1

    exec_svc.next_question(room_id)
    state = exec_svc.get_execution_state(room_id)
    assert state.question is not None
    q2_opts = [str(o.id) for o in sorted(state.question.options, key=lambda o: o.sort_order)]
    resp_svc.submit(
        room_id=room_id,
        participant_id=pid,
        option_ids=[UUID(q2_opts[1])],
        require_connected=False,
    )
    exec_svc.close_question(room_id)
    exec_svc.reveal_answer(room_id)

    db_session.expire_all()
    p = db_session.get(Participant, pid)
    assert p is not None
    assert p.total_score == 5
    assert p.total_correct == 1
    assert p.total_incorrect == 1
    assert p.streak == 0


def test_admin_question_scored_broadcast(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room, option_ids, [joined] = _setup_open_question(
        client,
        admin_token,
        db_session,
        title="Score WS",
        joiners=[("Hal", "hal@example.com")],
    )
    ResponseService(db_session).submit(
        room_id=UUID(room["id"]),
        participant_id=UUID(joined["participant"]["id"]),
        option_ids=[UUID(option_ids[0])],
        require_connected=False,
    )

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
            _recv_until(admin_ws, ServerEventType.PARTICIPANT_JOINED)

            admin_ws.send_json({"type": "admin:close_question", "payload": {}})
            _recv_until(admin_ws, ServerEventType.QUESTION_CLOSED)
            _recv_until(part_ws, ServerEventType.QUESTION_CLOSED)

            admin_ws.send_json({"type": "admin:reveal_answer", "payload": {}})
            _recv_until(admin_ws, ServerEventType.QUESTION_REVEAL)
            scored = _recv_until(admin_ws, ServerEventType.QUESTION_SCORED)
            assert scored["payload"]["correctCount"] == 1
            assert "selectedOptionIds" not in scored["payload"]

            # Participant must not receive question:scored (admin-only).
            part_ws.send_json({"type": "ping", "payload": {}})
            pong = _recv_until(part_ws, ServerEventType.PONG)
            assert pong["type"] == "pong"


def test_question_marked_scored(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room, option_ids, [joined] = _setup_open_question(
        client,
        admin_token,
        db_session,
        title="Score State",
        joiners=[("Ivy", "ivy2@example.com")],
    )
    ResponseService(db_session).submit(
        room_id=UUID(room["id"]),
        participant_id=UUID(joined["participant"]["id"]),
        option_ids=[UUID(option_ids[0])],
        require_connected=False,
    )
    _close_and_reveal(db_session, UUID(room["id"]))
    state = QuizExecutionService(db_session).get_execution_state(UUID(room["id"]))
    assert state.question is not None
    assert state.question.state == SessionQuestionState.SCORED
