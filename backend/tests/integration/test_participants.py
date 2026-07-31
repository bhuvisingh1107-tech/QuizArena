"""Integration tests for Participant Management (API_SPEC.md §12)."""

from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import QuizStatus
from app.models.quiz import Quiz
from app.services import participant_service as participant_service_mod


def _auth_admin(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _auth_participant(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _build_ready_quiz(
    client: TestClient,
    admin_token: str,
    db_session: Session,
    *,
    title: str = "Participant Quiz",
) -> str:
    quiz = client.post(
        "/api/v1/quizzes",
        headers=_auth_admin(admin_token),
        json={"title": title},
    )
    assert quiz.status_code == 201, quiz.text
    quiz_id = quiz.json()["data"]["id"]

    section = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections",
        headers=_auth_admin(admin_token),
        json={"name": "Round 1"},
    )
    section_id = section.json()["data"]["id"]
    question = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections/{section_id}/questions",
        headers=_auth_admin(admin_token),
        json={"questionType": "Text", "promptText": "Q1"},
    )
    question_id = question.json()["data"]["id"]
    for text, correct, order in (("A", True, 0), ("B", False, 1)):
        client.post(
            f"/api/v1/quizzes/{quiz_id}/sections/{section_id}/questions/{question_id}/options",
            headers=_auth_admin(admin_token),
            json={"text": text, "isCorrect": correct, "sortOrder": order},
        )

    row = db_session.get(Quiz, UUID(quiz_id))
    assert row is not None
    row.status = QuizStatus.READY
    db_session.commit()
    return quiz_id


def _open_lobby_room(
    client: TestClient,
    admin_token: str,
    db_session: Session,
    *,
    title: str = "Lobby Room Quiz",
) -> dict:
    quiz_id = _build_ready_quiz(client, admin_token, db_session, title=title)
    room = client.post(
        "/api/v1/live-rooms",
        headers=_auth_admin(admin_token),
        json={"quizId": quiz_id},
    )
    assert room.status_code == 201, room.text
    room_id = room.json()["data"]["id"]
    lobby = client.post(
        f"/api/v1/live-rooms/{room_id}/open-lobby",
        headers=_auth_admin(admin_token),
    )
    assert lobby.status_code == 200, lobby.text
    return lobby.json()["data"]


def _join(
    client: TestClient,
    *,
    room_code: str,
    display_name: str = "Alex",
    email: str = "alex@example.com",
):
    return client.post(
        "/api/v1/join",
        json={
            "roomCode": room_code,
            "displayName": display_name,
            "email": email,
        },
    )


def test_successful_join(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room = _open_lobby_room(client, admin_token, db_session)
    response = _join(client, room_code=room["roomCode"])
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["restored"] is False
    assert data["sessionToken"]
    assert data["participant"]["displayName"] == "Alex"
    assert data["participant"]["email"] == "alex@example.com"
    assert data["participant"]["state"] == "InLobby"
    assert data["participant"]["totalScore"] == 0
    assert data["room"]["roomCode"] == room["roomCode"]
    assert data["room"]["state"] == "Lobby"


def test_invalid_room_code(client: TestClient) -> None:
    response = _join(client, room_code="ZZZZZZ")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "INVALID_ROOM_CODE"


def test_room_closed(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room = _open_lobby_room(client, admin_token, db_session, title="Close Join Quiz")
    room_id = room["id"]
    client.post(f"/api/v1/live-rooms/{room_id}/close", headers=_auth_admin(admin_token))
    response = _join(client, room_code=room["roomCode"])
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "ROOM_CLOSED"


def test_room_completed(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room = _open_lobby_room(client, admin_token, db_session, title="Complete Join Quiz")
    room_id = room["id"]
    client.post(f"/api/v1/live-rooms/{room_id}/start", headers=_auth_admin(admin_token))
    client.post(f"/api/v1/live-rooms/{room_id}/end", headers=_auth_admin(admin_token))
    response = _join(client, room_code=room["roomCode"])
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "ROOM_COMPLETED"


def test_room_full(
    client: TestClient,
    admin_token: str,
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(participant_service_mod, "_MAX_PARTICIPANTS_PER_ROOM", 1)
    room = _open_lobby_room(client, admin_token, db_session, title="Full Room Quiz")
    first = _join(
        client,
        room_code=room["roomCode"],
        display_name="One",
        email="one@example.com",
    )
    assert first.status_code == 201
    second = _join(
        client,
        room_code=room["roomCode"],
        display_name="Two",
        email="two@example.com",
    )
    assert second.status_code == 422
    assert second.json()["error"]["code"] == "ROOM_FULL"


def test_duplicate_name(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room = _open_lobby_room(client, admin_token, db_session, title="Dup Name Quiz")
    first = _join(
        client,
        room_code=room["roomCode"],
        display_name="Sam",
        email="sam1@example.com",
    )
    assert first.status_code == 201
    second = _join(
        client,
        room_code=room["roomCode"],
        display_name="Sam",
        email="sam2@example.com",
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "DUPLICATE_DISPLAY_NAME"


def test_invalid_participant_token(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    _open_lobby_room(client, admin_token, db_session, title="Bad Token Quiz")
    response = client.get(
        "/api/v1/participants/me",
        headers=_auth_participant("not-a-real-token"),
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_PARTICIPANT_TOKEN"


def test_successful_reconnect(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room = _open_lobby_room(client, admin_token, db_session, title="Reconnect Quiz")
    joined = _join(client, room_code=room["roomCode"]).json()["data"]
    token = joined["sessionToken"]
    score_before = joined["participant"]["totalScore"]

    # Simulate disconnect via leave, then token reconnect
    left = client.post("/api/v1/participants/leave", headers=_auth_participant(token))
    assert left.status_code == 200
    assert left.json()["data"]["state"] == "Disconnected"

    reconnected = client.post(
        "/api/v1/participants/reconnect",
        headers=_auth_participant(token),
    )
    assert reconnected.status_code == 200, reconnected.text
    data = reconnected.json()["data"]
    assert data["restored"] is True
    assert data["sessionToken"] == token
    assert data["participant"]["totalScore"] == score_before
    assert data["participant"]["state"] == "InLobby"
    assert data["participant"]["connectionStatus"] == "connected"


def test_failed_reconnect(client: TestClient) -> None:
    response = client.post(
        "/api/v1/participants/reconnect",
        headers=_auth_participant("missing-token-value-xxxxxx"),
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_PARTICIPANT_TOKEN"


def test_leave_room(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room = _open_lobby_room(client, admin_token, db_session, title="Leave Quiz")
    token = _join(
        client,
        room_code=room["roomCode"],
        display_name="Leaver",
        email="leave@example.com",
    ).json()["data"]["sessionToken"]

    response = client.post("/api/v1/participants/leave", headers=_auth_participant(token))
    assert response.status_code == 200
    assert response.json()["data"]["left"] is True
    assert response.json()["data"]["state"] == "Disconnected"

    me = client.get("/api/v1/participants/me", headers=_auth_participant(token))
    assert me.status_code == 200
    assert me.json()["data"]["participant"]["state"] == "Disconnected"


def test_email_rejoin_restores_session(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room = _open_lobby_room(client, admin_token, db_session, title="Email Rejoin Quiz")
    first = _join(
        client,
        room_code=room["roomCode"],
        display_name="Riley",
        email="riley@example.com",
    )
    assert first.status_code == 201
    participant_id = first.json()["data"]["participant"]["id"]
    old_token = first.json()["data"]["sessionToken"]

    restored = _join(
        client,
        room_code=room["roomCode"],
        display_name="Riley",
        email="riley@example.com",
    )
    assert restored.status_code == 200, restored.text
    data = restored.json()["data"]
    assert data["restored"] is True
    assert data["participant"]["id"] == participant_id
    assert data["sessionToken"] != old_token


def test_lobby_closed_rejects_new_joins(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room = _open_lobby_room(client, admin_token, db_session, title="Lobby Closed Quiz")
    client.post(
        f"/api/v1/live-rooms/{room['id']}/toggle-lobby",
        headers=_auth_admin(admin_token),
    )
    response = _join(
        client,
        room_code=room["roomCode"],
        display_name="Blocked",
        email="blocked@example.com",
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "ROOM_NOT_ACCEPTING_JOINS"


def test_unauthorized_admin_endpoint_isolation(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room = _open_lobby_room(client, admin_token, db_session, title="Isolation Quiz")
    token = _join(
        client,
        room_code=room["roomCode"],
        display_name="Iso",
        email="iso@example.com",
    ).json()["data"]["sessionToken"]

    # Participant token cannot access admin quiz APIs
    forbidden = client.get("/api/v1/quizzes", headers=_auth_participant(token))
    assert forbidden.status_code == 401

    # Join does not require admin JWT
    other = _join(
        client,
        room_code=room["roomCode"],
        display_name="Guest",
        email="guest@example.com",
    )
    assert other.status_code == 201

    # Missing token on participant endpoint
    missing = client.get("/api/v1/participants/me")
    assert missing.status_code == 401


def test_get_participant(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room = _open_lobby_room(client, admin_token, db_session, title="Get Me Quiz")
    joined = _join(
        client,
        room_code=room["roomCode"],
        display_name="Pat",
        email="pat@example.com",
    ).json()["data"]
    response = client.get(
        "/api/v1/participants/me",
        headers=_auth_participant(joined["sessionToken"]),
    )
    assert response.status_code == 200
    assert response.json()["data"]["participant"]["id"] == joined["participant"]["id"]
    assert response.json()["data"]["room"]["id"] == room["id"]
