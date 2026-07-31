"""Integration tests for Live Room Management (API_SPEC.md §11)."""

from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import QuizStatus
from app.models.quiz import Quiz


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _build_ready_quiz(
    client: TestClient,
    token: str,
    db_session: Session,
    *,
    title: str = "Ready Live Quiz",
) -> str:
    quiz = client.post(
        "/api/v1/quizzes",
        headers=_auth(token),
        json={"title": title},
    )
    assert quiz.status_code == 201, quiz.text
    quiz_id = quiz.json()["data"]["id"]

    section = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections",
        headers=_auth(token),
        json={"name": "Round 1"},
    )
    assert section.status_code == 201, section.text
    section_id = section.json()["data"]["id"]

    question = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections/{section_id}/questions",
        headers=_auth(token),
        json={"questionType": "Text", "promptText": "Capital of France?"},
    )
    assert question.status_code == 201, question.text
    question_id = question.json()["data"]["id"]

    for text, correct, order in (("Paris", True, 0), ("London", False, 1)):
        option = client.post(
            f"/api/v1/quizzes/{quiz_id}/sections/{section_id}/questions/{question_id}/options",
            headers=_auth(token),
            json={"text": text, "isCorrect": correct, "sortOrder": order},
        )
        assert option.status_code == 201, option.text

    row = db_session.get(Quiz, UUID(quiz_id))
    assert row is not None
    row.status = QuizStatus.READY
    db_session.commit()
    return quiz_id


def _create_room(client: TestClient, token: str, quiz_id: str):
    return client.post(
        "/api/v1/live-rooms",
        headers=_auth(token),
        json={"quizId": quiz_id},
    )


def test_create_room(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    quiz_id = _build_ready_quiz(client, admin_token, db_session)
    response = _create_room(client, admin_token, quiz_id)
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["state"] == "Setup"
    assert data["quizId"] == quiz_id
    assert len(data["roomCode"]) == 6
    assert data["roomCode"].isalnum()
    assert data["sectionCount"] == 1
    assert data["questionCount"] == 1
    assert data["config"] is not None
    assert data["joinUrl"].endswith(f"/join/{data['roomCode']}")
    assert data["codesExpired"] is False

    quiz = client.get(f"/api/v1/quizzes/{quiz_id}", headers=_auth(admin_token))
    assert quiz.json()["data"]["status"] == "InUse"


def test_create_from_invalid_quiz(client: TestClient, admin_token: str) -> None:
    response = _create_room(client, admin_token, str(uuid4()))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "QUIZ_NOT_FOUND"


def test_create_from_draft_quiz(client: TestClient, admin_token: str) -> None:
    quiz = client.post(
        "/api/v1/quizzes",
        headers=_auth(admin_token),
        json={"title": "Still Draft"},
    )
    assert quiz.status_code == 201
    response = _create_room(client, admin_token, quiz.json()["data"]["id"])
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "QUIZ_NOT_READY"


def test_list_rooms(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    quiz_id = _build_ready_quiz(client, admin_token, db_session, title="List Rooms Quiz")
    created = _create_room(client, admin_token, quiz_id)
    assert created.status_code == 201

    response = client.get("/api/v1/live-rooms", headers=_auth(admin_token))
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["total"] >= 1
    assert any(item["id"] == created.json()["data"]["id"] for item in body["items"])


def test_get_room(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    quiz_id = _build_ready_quiz(client, admin_token, db_session, title="Get Room Quiz")
    created = _create_room(client, admin_token, quiz_id).json()["data"]
    response = client.get(
        f"/api/v1/live-rooms/{created['id']}",
        headers=_auth(admin_token),
    )
    assert response.status_code == 200
    assert response.json()["data"]["id"] == created["id"]
    assert response.json()["data"]["roomCode"] == created["roomCode"]


def test_update_room_config(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    quiz_id = _build_ready_quiz(client, admin_token, db_session, title="Config Room Quiz")
    room = _create_room(client, admin_token, quiz_id).json()["data"]

    response = client.patch(
        f"/api/v1/live-rooms/{room['id']}/config",
        headers=_auth(admin_token),
        json={"timeBonusEnabled": True, "timeBonusMaxPoints": 5},
    )
    assert response.status_code == 200, response.text
    config = response.json()["data"]["config"]
    assert config["timeBonusEnabled"] is True
    assert config["timeBonusMaxPoints"] == 5

    # Immutable after lobby opens
    client.post(
        f"/api/v1/live-rooms/{room['id']}/open-lobby",
        headers=_auth(admin_token),
    )
    blocked = client.patch(
        f"/api/v1/live-rooms/{room['id']}/config",
        headers=_auth(admin_token),
        json={"timeBonusEnabled": False},
    )
    assert blocked.status_code == 422
    assert blocked.json()["error"]["code"] == "ROOM_CONFIG_IMMUTABLE"


def test_start_and_finish_room(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    quiz_id = _build_ready_quiz(client, admin_token, db_session, title="Start Finish Quiz")
    room_id = _create_room(client, admin_token, quiz_id).json()["data"]["id"]

    lobby = client.post(
        f"/api/v1/live-rooms/{room_id}/open-lobby",
        headers=_auth(admin_token),
    )
    assert lobby.status_code == 200
    assert lobby.json()["data"]["state"] == "Lobby"
    assert lobby.json()["data"]["lobbySubState"] == "LobbyOpen"

    started = client.post(
        f"/api/v1/live-rooms/{room_id}/start",
        headers=_auth(admin_token),
    )
    assert started.status_code == 200
    assert started.json()["data"]["state"] == "Active"
    assert started.json()["data"]["currentQuestionIndex"] == 0

    ended = client.post(
        f"/api/v1/live-rooms/{room_id}/end",
        headers=_auth(admin_token),
    )
    assert ended.status_code == 200
    assert ended.json()["data"]["state"] == "Completed"
    assert ended.json()["data"]["completedAt"] is not None


def test_invalid_transitions(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    quiz_id = _build_ready_quiz(client, admin_token, db_session, title="Bad Transition Quiz")
    room_id = _create_room(client, admin_token, quiz_id).json()["data"]["id"]

    # Cannot start from Setup
    bad_start = client.post(
        f"/api/v1/live-rooms/{room_id}/start",
        headers=_auth(admin_token),
    )
    assert bad_start.status_code == 422
    assert bad_start.json()["error"]["code"] == "INVALID_STATE_TRANSITION"

    client.post(f"/api/v1/live-rooms/{room_id}/open-lobby", headers=_auth(admin_token))
    client.post(f"/api/v1/live-rooms/{room_id}/start", headers=_auth(admin_token))

    # Cannot start an already running room
    again = client.post(
        f"/api/v1/live-rooms/{room_id}/start",
        headers=_auth(admin_token),
    )
    assert again.status_code == 422
    assert again.json()["error"]["code"] == "INVALID_STATE_TRANSITION"

    client.post(f"/api/v1/live-rooms/{room_id}/end", headers=_auth(admin_token))

    # Cannot start a finished room
    finished = client.post(
        f"/api/v1/live-rooms/{room_id}/start",
        headers=_auth(admin_token),
    )
    assert finished.status_code == 422
    assert finished.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


def test_delete_room(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    quiz_id = _build_ready_quiz(client, admin_token, db_session, title="Delete Room Quiz")
    room_id = _create_room(client, admin_token, quiz_id).json()["data"]["id"]

    response = client.delete(
        f"/api/v1/live-rooms/{room_id}",
        headers=_auth(admin_token),
    )
    assert response.status_code == 200
    assert response.json()["data"]["deleted"] is True

    missing = client.get(f"/api/v1/live-rooms/{room_id}", headers=_auth(admin_token))
    assert missing.status_code == 404

    quiz = client.get(f"/api/v1/quizzes/{quiz_id}", headers=_auth(admin_token))
    assert quiz.json()["data"]["status"] == "Ready"


def test_unauthorized(client: TestClient) -> None:
    response = client.get("/api/v1/live-rooms")
    assert response.status_code == 401


def test_duplicate_join_code_handling(
    client: TestClient,
    admin_token: str,
    db_session: Session,
    monkeypatch,
) -> None:
    """Generator retries when a candidate code already exists in the database."""
    from app.services import live_room_service as svc_mod

    quiz_a = _build_ready_quiz(client, admin_token, db_session, title="Code Quiz A")
    room_a = _create_room(client, admin_token, quiz_a)
    assert room_a.status_code == 201
    room_a_id = room_a.json()["data"]["id"]
    existing_code = room_a.json()["data"]["roomCode"]

    # Keep the code row in DB by closing (not deleting) the first room.
    client.post(f"/api/v1/live-rooms/{room_a_id}/open-lobby", headers=_auth(admin_token))
    client.post(f"/api/v1/live-rooms/{room_a_id}/start", headers=_auth(admin_token))
    client.post(f"/api/v1/live-rooms/{room_a_id}/end", headers=_auth(admin_token))
    closed = client.post(f"/api/v1/live-rooms/{room_a_id}/close", headers=_auth(admin_token))
    assert closed.status_code == 200

    quiz_b = _build_ready_quiz(client, admin_token, db_session, title="Code Quiz B")

    calls = {"n": 0}
    real_choice = svc_mod.secrets.choice

    def _choice(seq):
        # First 6 calls rebuild the colliding code; later calls are random.
        calls["n"] += 1
        if calls["n"] <= 6:
            return existing_code[calls["n"] - 1]
        return real_choice(seq)

    monkeypatch.setattr(svc_mod.secrets, "choice", _choice)

    room_b = _create_room(client, admin_token, quiz_b)
    assert room_b.status_code == 201, room_b.text
    assert room_b.json()["data"]["roomCode"] != existing_code


def test_single_active_room_constraint(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    quiz_a = _build_ready_quiz(client, admin_token, db_session, title="Active A")
    assert _create_room(client, admin_token, quiz_a).status_code == 201

    quiz_b = _build_ready_quiz(client, admin_token, db_session, title="Active B")
    # Mark ready manually — still blocked by hosting room constraint
    conflict = _create_room(client, admin_token, quiz_b)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "ACTIVE_ROOM_EXISTS"


def test_snapshot_immutable_to_quiz_edits(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    quiz_id = _build_ready_quiz(client, admin_token, db_session, title="Snapshot Quiz")
    room = _create_room(client, admin_token, quiz_id).json()["data"]
    assert room["questionCount"] == 1

    # Soft-delete room first so quiz becomes Ready and editable? Quiz is InUse — edits blocked.
    # Close path: delete Setup room restores Ready, but we need to prove snapshot isolation
    # while room exists. Force quiz title change via ORM (simulating template change).
    quiz_row = db_session.get(Quiz, UUID(quiz_id))
    assert quiz_row is not None
    quiz_row.title = "Changed After Snapshot"
    db_session.commit()

    detail = client.get(
        f"/api/v1/live-rooms/{room['id']}",
        headers=_auth(admin_token),
    )
    assert detail.json()["data"]["quizTitleSnapshot"] == "Snapshot Quiz"
    assert detail.json()["data"]["questionCount"] == 1


def test_pause_resume_and_close(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    quiz_id = _build_ready_quiz(client, admin_token, db_session, title="Pause Close Quiz")
    room_id = _create_room(client, admin_token, quiz_id).json()["data"]["id"]
    client.post(f"/api/v1/live-rooms/{room_id}/open-lobby", headers=_auth(admin_token))
    client.post(f"/api/v1/live-rooms/{room_id}/start", headers=_auth(admin_token))

    paused = client.post(f"/api/v1/live-rooms/{room_id}/pause", headers=_auth(admin_token))
    assert paused.json()["data"]["state"] == "Paused"

    resumed = client.post(f"/api/v1/live-rooms/{room_id}/resume", headers=_auth(admin_token))
    assert resumed.json()["data"]["state"] == "Active"

    client.post(f"/api/v1/live-rooms/{room_id}/end", headers=_auth(admin_token))
    closed = client.post(f"/api/v1/live-rooms/{room_id}/close", headers=_auth(admin_token))
    assert closed.status_code == 200
    assert closed.json()["data"]["state"] == "Closed"
    assert closed.json()["data"]["codesExpired"] is True

    quiz = client.get(f"/api/v1/quizzes/{quiz_id}", headers=_auth(admin_token))
    assert quiz.json()["data"]["status"] == "Ready"
