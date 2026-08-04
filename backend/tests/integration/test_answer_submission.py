"""Integration tests for Answer Submission module."""

from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.websocket.events import ServerEventType
from app.core.exceptions import (
    AuthorizationError,
    NotFoundError,
    ValidationError,
)
from app.models.enums import (
    ConnectionStatus,
    ParticipantState,
    QuizStatus,
    RoomState,
)
from app.models.participant import Participant
from app.models.quiz import Quiz
from app.models.response import Response
from app.models.room_ban import RoomBan
from app.services.quiz_execution_service import QuizExecutionService
from app.services.response_service import ResponseService


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _add_question(
    client: TestClient,
    token: str,
    quiz_id: str,
    section_id: str,
    prompt: str,
) -> str:
    q = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections/{section_id}/questions",
        headers=_auth(token),
        json={"questionType": "Text", "promptText": prompt},
    )
    assert q.status_code == 201, q.text
    q_id = q.json()["data"]["id"]
    for text, correct, order in (("Yes", True, 0), ("No", False, 1)):
        opt = client.post(
            f"/api/v1/quizzes/{quiz_id}/sections/{section_id}/questions/{q_id}/options",
            headers=_auth(token),
            json={"text": text, "isCorrect": correct, "sortOrder": order},
        )
        assert opt.status_code == 201, opt.text
    return q_id


def _ready_quiz(client: TestClient, token: str, db: Session, title: str) -> str:
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
    _add_question(client, token, quiz_id, section_id, "Capital?")
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


def _active_room_with_question(
    client: TestClient,
    token: str,
    db: Session,
    *,
    title: str,
    joiners: list[tuple[str, str]] | None = None,
) -> tuple[dict, list[str], list[dict]]:
    """Return (room, option ids, joined participants) with first question Open."""
    quiz_id = _ready_quiz(client, token, db, title)
    room = client.post(
        "/api/v1/live-rooms",
        headers=_auth(token),
        json={"quizId": quiz_id},
    ).json()["data"]
    client.post(f"/api/v1/live-rooms/{room['id']}/open-lobby", headers=_auth(token))

    joined: list[dict] = []
    for name, email in joiners or []:
        joined.append(_join(client, room["roomCode"], name, email))

    client.post(f"/api/v1/live-rooms/{room['id']}/start", headers=_auth(token))
    svc = QuizExecutionService(db)
    result = svc.start_first_question(UUID(room["id"]))
    question = sorted(result.room.session_questions, key=lambda q: q.sort_order)[0]
    option_ids = [str(o.id) for o in sorted(question.options, key=lambda o: o.sort_order)]
    room = client.get(
        f"/api/v1/live-rooms/{room['id']}",
        headers=_auth(token),
    ).json()["data"]
    return room, option_ids, joined


def _recv_until(ws, event_type: str, *, limit: int = 30) -> dict:
    for _ in range(limit):
        msg = ws.receive_json()
        if msg.get("type") == event_type:
            return msg
    raise AssertionError(f"Did not receive {event_type}")


def test_successful_submission(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room, option_ids, [joined] = _active_room_with_question(
        client,
        admin_token,
        db_session,
        title="Submit OK",
        joiners=[("Alice", "alice@example.com")],
    )

    with client.websocket_connect(
        f"/ws?role=participant&token={joined['sessionToken']}",
    ) as ws:
        _recv_until(ws, ServerEventType.CONNECTION_ACK)
        _recv_until(ws, ServerEventType.RESYNC)
        ws.send_json(
            {"type": "answer:submit", "payload": {"optionIds": [option_ids[0]]}},
        )
        accepted = _recv_until(ws, ServerEventType.ANSWER_ACCEPTED)
        assert accepted["payload"]["status"] == "submitted"
        assert accepted["payload"]["selectedOptionIds"] == [option_ids[0]]
        assert "pointsEarned" not in accepted["payload"]
        assert "totalScore" not in accepted["payload"]
        assert "streak" not in accepted["payload"]
        assert "isCorrect" not in accepted["payload"]

    db_session.expire_all()
    rows = list(db_session.scalars(select(Response)).all())
    assert len(rows) == 1
    # Pre-reveal: selection stored, scoring deferred until reveal.
    assert rows[0].status == "submitted"
    assert rows[0].is_correct is False
    assert rows[0].selected_option_ids == [option_ids[0]]
    assert rows[0].scored_at is None
    assert rows[0].total_points_earned == 0


def test_duplicate_submission(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room, option_ids, [joined] = _active_room_with_question(
        client,
        admin_token,
        db_session,
        title="Submit Dup",
        joiners=[("Bob", "bob@example.com")],
    )
    svc = ResponseService(db_session)
    svc.submit(
        room_id=UUID(room["id"]),
        participant_id=UUID(joined["participant"]["id"]),
        option_ids=[UUID(option_ids[0])],
        require_connected=False,
    )
    try:
        svc.submit(
            room_id=UUID(room["id"]),
            participant_id=UUID(joined["participant"]["id"]),
            option_ids=[UUID(option_ids[1])],
            require_connected=False,
        )
        raise AssertionError("expected ALREADY_SUBMITTED")
    except ValidationError as exc:
        assert exc.code == "ALREADY_SUBMITTED"

    db_session.expire_all()
    rows = list(db_session.scalars(select(Response)).all())
    assert len(rows) == 1
    assert rows[0].selected_option_ids == [option_ids[0]]


def test_invalid_option(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room, _option_ids, [joined] = _active_room_with_question(
        client,
        admin_token,
        db_session,
        title="Submit Bad Opt",
        joiners=[("Carol", "carol@example.com")],
    )
    svc = ResponseService(db_session)
    try:
        svc.submit(
            room_id=UUID(room["id"]),
            participant_id=UUID(joined["participant"]["id"]),
            option_ids=[uuid4()],
            require_connected=False,
        )
        raise AssertionError("expected INVALID_OPTION")
    except ValidationError as exc:
        assert exc.code == "INVALID_OPTION"


def test_invalid_room(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room, option_ids, [joined] = _active_room_with_question(
        client,
        admin_token,
        db_session,
        title="Submit Bad Room",
        joiners=[("Dan", "dan@example.com")],
    )
    svc = ResponseService(db_session)
    try:
        svc.submit(
            room_id=uuid4(),
            participant_id=UUID(joined["participant"]["id"]),
            option_ids=[UUID(option_ids[0])],
            require_connected=False,
        )
        raise AssertionError("expected FORBIDDEN")
    except AuthorizationError as exc:
        assert exc.code == "FORBIDDEN"


def test_invalid_participant(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room, option_ids, _joined = _active_room_with_question(
        client,
        admin_token,
        db_session,
        title="Submit Bad Part",
        joiners=[("X", "x@example.com")],
    )
    svc = ResponseService(db_session)
    try:
        svc.submit(
            room_id=UUID(room["id"]),
            participant_id=uuid4(),
            option_ids=[UUID(option_ids[0])],
            require_connected=False,
        )
        raise AssertionError("expected NOT_FOUND")
    except NotFoundError as exc:
        assert exc.code == "NOT_FOUND"


def test_banned_participant(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room, option_ids, [joined] = _active_room_with_question(
        client,
        admin_token,
        db_session,
        title="Submit Banned",
        joiners=[("Eve", "eve@example.com")],
    )
    pid = UUID(joined["participant"]["id"])
    participant = db_session.get(Participant, pid)
    assert participant is not None
    participant.state = ParticipantState.BANNED
    db_session.add(RoomBan(live_room_id=UUID(room["id"]), email="eve@example.com"))
    db_session.commit()

    svc = ResponseService(db_session)
    try:
        svc.submit(
            room_id=UUID(room["id"]),
            participant_id=pid,
            option_ids=[UUID(option_ids[0])],
            require_connected=False,
        )
        raise AssertionError("expected FORBIDDEN")
    except AuthorizationError as exc:
        assert exc.code == "FORBIDDEN"


def test_closed_question(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room, option_ids, [joined] = _active_room_with_question(
        client,
        admin_token,
        db_session,
        title="Submit Closed",
        joiners=[("Frank", "frank@example.com")],
    )
    QuizExecutionService(db_session).close_question(UUID(room["id"]))
    svc = ResponseService(db_session)
    try:
        svc.submit(
            room_id=UUID(room["id"]),
            participant_id=UUID(joined["participant"]["id"]),
            option_ids=[UUID(option_ids[0])],
            require_connected=False,
        )
        raise AssertionError("expected QUESTION_CLOSED")
    except ValidationError as exc:
        assert exc.code == "QUESTION_CLOSED"


def test_completed_quiz(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room, option_ids, [joined] = _active_room_with_question(
        client,
        admin_token,
        db_session,
        title="Submit Done",
        joiners=[("Gina", "gina@example.com")],
    )
    QuizExecutionService(db_session).end_quiz(UUID(room["id"]))
    svc = ResponseService(db_session)
    try:
        svc.submit(
            room_id=UUID(room["id"]),
            participant_id=UUID(joined["participant"]["id"]),
            option_ids=[UUID(option_ids[0])],
            require_connected=False,
        )
        raise AssertionError("expected ROOM_COMPLETED")
    except ValidationError as exc:
        assert exc.code == "ROOM_COMPLETED"


def test_disconnected_participant(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room, option_ids, [joined] = _active_room_with_question(
        client,
        admin_token,
        db_session,
        title="Submit Disc",
        joiners=[("Hank", "hank@example.com")],
    )
    pid = UUID(joined["participant"]["id"])
    participant = db_session.get(Participant, pid)
    assert participant is not None
    participant.connection_status = ConnectionStatus.DISCONNECTED
    participant.state = ParticipantState.DISCONNECTED
    db_session.commit()

    svc = ResponseService(db_session)
    try:
        svc.submit(
            room_id=UUID(room["id"]),
            participant_id=pid,
            option_ids=[UUID(option_ids[0])],
            require_connected=True,
        )
        raise AssertionError("expected FORBIDDEN")
    except AuthorizationError as exc:
        assert exc.code == "FORBIDDEN"


def test_multiple_participants_and_admin_counter(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room, option_ids, [p1, p2] = _active_room_with_question(
        client,
        admin_token,
        db_session,
        title="Submit Multi",
        joiners=[("Ivy", "ivy@example.com"), ("Jay", "jay@example.com")],
    )

    with client.websocket_connect(
        f"/ws?role=admin&token={admin_token}&roomId={room['id']}",
    ) as admin_ws:
        _recv_until(admin_ws, ServerEventType.CONNECTION_ACK)
        _recv_until(admin_ws, ServerEventType.RESYNC)

        with client.websocket_connect(
            f"/ws?role=participant&token={p1['sessionToken']}",
        ) as ws1:
            _recv_until(ws1, ServerEventType.CONNECTION_ACK)
            _recv_until(ws1, ServerEventType.RESYNC)
            _recv_until(admin_ws, ServerEventType.PARTICIPANT_JOINED)

            with client.websocket_connect(
                f"/ws?role=participant&token={p2['sessionToken']}",
            ) as ws2:
                _recv_until(ws2, ServerEventType.CONNECTION_ACK)
                _recv_until(ws2, ServerEventType.RESYNC)
                _recv_until(admin_ws, ServerEventType.PARTICIPANT_JOINED)

                ws1.send_json(
                    {"type": "answer:submit", "payload": {"optionIds": [option_ids[0]]}},
                )
                _recv_until(ws1, ServerEventType.ANSWER_ACCEPTED)
                count1 = _recv_until(admin_ws, ServerEventType.ANSWER_SUBMISSION_COUNT)
                assert count1["payload"]["submittedCount"] == 1
                assert "selectedOptionIds" not in count1["payload"]

                ws2.send_json(
                    {"type": "answer:submit", "payload": {"optionIds": [option_ids[1]]}},
                )
                _recv_until(ws2, ServerEventType.ANSWER_ACCEPTED)
                count2 = _recv_until(admin_ws, ServerEventType.ANSWER_SUBMISSION_COUNT)
                assert count2["payload"]["submittedCount"] == 2


def test_reconnect_then_submit(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room, option_ids, [joined] = _active_room_with_question(
        client,
        admin_token,
        db_session,
        title="Submit Reconn",
        joiners=[("Kim", "kim@example.com")],
    )

    with client.websocket_connect(
        f"/ws?role=participant&token={joined['sessionToken']}",
    ) as ws:
        _recv_until(ws, ServerEventType.CONNECTION_ACK)
        _recv_until(ws, ServerEventType.RESYNC)

    with client.websocket_connect(
        f"/ws?role=participant&token={joined['sessionToken']}",
    ) as ws2:
        _recv_until(ws2, ServerEventType.CONNECTION_ACK)
        resync = _recv_until(ws2, ServerEventType.RESYNC)
        assert resync["payload"]["submission"]["hasSubmitted"] is False
        assert resync["payload"]["question"]["isAcceptingAnswers"] is True
        ws2.send_json(
            {"type": "answer:submit", "payload": {"optionIds": [option_ids[0]]}},
        )
        accepted = _recv_until(ws2, ServerEventType.ANSWER_ACCEPTED)
        assert accepted["payload"]["status"] == "submitted"


def test_reconnect_after_submission(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room, option_ids, [joined] = _active_room_with_question(
        client,
        admin_token,
        db_session,
        title="Submit Resync",
        joiners=[("Lee", "lee@example.com")],
    )
    ResponseService(db_session).submit(
        room_id=UUID(room["id"]),
        participant_id=UUID(joined["participant"]["id"]),
        option_ids=[UUID(option_ids[0])],
        require_connected=False,
    )

    with client.websocket_connect(
        f"/ws?role=participant&token={joined['sessionToken']}",
    ) as ws:
        _recv_until(ws, ServerEventType.CONNECTION_ACK)
        resync = _recv_until(ws, ServerEventType.RESYNC)
        assert resync["payload"]["submission"]["hasSubmitted"] is True
        assert resync["payload"]["submission"]["selectedOptionIds"] == [option_ids[0]]
        assert resync["payload"]["participant"]["hasSubmitted"] is True


def test_persistence_fields(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room, option_ids, [joined] = _active_room_with_question(
        client,
        admin_token,
        db_session,
        title="Submit Persist",
        joiners=[("Mo", "mo@example.com")],
    )
    result = ResponseService(db_session).submit(
        room_id=UUID(room["id"]),
        participant_id=UUID(joined["participant"]["id"]),
        option_ids=[UUID(option_ids[0])],
        require_connected=False,
    )
    row = result.response
    assert row.participant_id == UUID(joined["participant"]["id"])
    assert row.session_question_id is not None
    assert row.selected_option_ids == [option_ids[0]]
    assert row.submitted_at is not None
    assert row.response_time_ms is not None
    assert row.response_time_ms >= 0
    assert row.status == "submitted"
    assert row.is_correct is False
    assert row.total_points_earned == 0
    assert row.scored_at is None

    db_session.expire_all()
    room_row = QuizExecutionService(db_session).get_execution_state(UUID(room["id"])).room
    assert room_row.state == RoomState.ACTIVE


def test_submit_after_start_quiz_while_participant_already_connected(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    """Regression: participant WS must not keep stale Lobby after host Start Quiz.

    Connect while room is Lobby, then host opens the quiz. Question 1 and submit
    must use the same committed Active state.
    """
    quiz_id = _ready_quiz(client, admin_token, db_session, "Stale Lobby Submit")
    room = client.post(
        "/api/v1/live-rooms",
        headers=_auth(admin_token),
        json={"quizId": quiz_id},
    ).json()["data"]
    client.post(f"/api/v1/live-rooms/{room['id']}/open-lobby", headers=_auth(admin_token))
    joined = _join(client, room["roomCode"], "Casey", "casey@example.com")

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
        assert started.status_code == 200, started.text
        assert started.json()["data"]["state"] == "Active"

        question_event = _recv_until(pws, ServerEventType.QUESTION_STARTED)
        question = question_event["payload"]["question"]
        assert question["state"] == "Open"
        option_ids = [o["id"] for o in question["options"]]
        assert option_ids

        pws.send_json(
            {"type": "answer:submit", "payload": {"optionIds": [option_ids[0]]}},
        )
        accepted = _recv_until(pws, ServerEventType.ANSWER_ACCEPTED)
        assert accepted["payload"]["status"] == "submitted"

    db_session.expire_all()
    room_row = QuizExecutionService(db_session).get_execution_state(UUID(room["id"])).room
    assert room_row.state == RoomState.ACTIVE
    responses = list(
        db_session.scalars(
            select(Response).where(Response.participant_id == UUID(joined["participant"]["id"]))
        ).all()
    )
    assert len(responses) == 1
    assert responses[0].submitted_at is not None
    assert responses[0].status == "submitted"
