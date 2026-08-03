"""Integration tests for admin participants, results, password, and dashboard."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import QuizStatus
from app.models.participant import Participant
from app.models.quiz import Quiz
from app.models.response import Response
from tests.conftest import TEST_PASSWORD, TEST_USERNAME


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _build_ready_quiz(
    client: TestClient,
    token: str,
    db_session: Session,
    *,
    title: str = "Admin Results Quiz",
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


def _open_lobby_room(client: TestClient, token: str, db_session: Session) -> dict:
    quiz_id = _build_ready_quiz(client, token, db_session)
    room = client.post(
        "/api/v1/live-rooms",
        headers=_auth(token),
        json={"quizId": quiz_id},
    )
    assert room.status_code == 201, room.text
    room_id = room.json()["data"]["id"]
    lobby = client.post(
        f"/api/v1/live-rooms/{room_id}/open-lobby",
        headers=_auth(token),
    )
    assert lobby.status_code == 200, lobby.text
    return lobby.json()["data"]


def _join(
    client: TestClient,
    *,
    room_code: str,
    display_name: str,
    email: str,
):
    return client.post(
        "/api/v1/join",
        json={
            "roomCode": room_code,
            "displayName": display_name,
            "email": email,
        },
    )


def test_list_room_participants(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room = _open_lobby_room(client, admin_token, db_session)
    first = _join(
        client,
        room_code=room["roomCode"],
        display_name="Alex",
        email="alex@example.com",
    )
    assert first.status_code == 201, first.text
    second = _join(
        client,
        room_code=room["roomCode"],
        display_name="Blake",
        email="blake@example.com",
    )
    assert second.status_code == 201, second.text

    # Raise Alex's score so ranking is deterministic
    alex = db_session.get(Participant, UUID(first.json()["data"]["participant"]["id"]))
    assert alex is not None
    alex.total_score = 50
    alex.total_correct = 1
    db_session.commit()

    response = client.get(
        f"/api/v1/live-rooms/{room['id']}/participants",
        headers=_auth(admin_token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["meta"]["requestId"]
    data = body["data"]
    assert data["total"] == 2
    assert len(data["items"]) == 2

    top = data["items"][0]
    assert top["displayName"] == "Alex"
    assert top["email"] == "alex@example.com"
    assert top["totalScore"] == 50
    assert top["rank"] == 1
    assert "connectionStatus" in top
    assert "joinedAt" in top
    assert data["items"][1]["rank"] == 2


def test_list_room_participants_requires_auth(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room = _open_lobby_room(client, admin_token, db_session)
    response = client.get(f"/api/v1/live-rooms/{room['id']}/participants")
    assert response.status_code == 401


def test_room_results_and_export(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room = _open_lobby_room(client, admin_token, db_session)
    joined = _join(
        client,
        room_code=room["roomCode"],
        display_name="Casey",
        email="casey@example.com",
    )
    assert joined.status_code == 201, joined.text
    participant_id = UUID(joined.json()["data"]["participant"]["id"])

    from app.models.live_room import LiveRoom

    live_room = db_session.get(LiveRoom, UUID(room["id"]))
    assert live_room is not None
    question = sorted(live_room.session_questions, key=lambda q: q.sort_order)[0]
    correct_option = next(o for o in question.options if o.is_correct)

    participant = db_session.get(Participant, participant_id)
    assert participant is not None
    participant.total_score = 10
    participant.total_correct = 1
    participant.streak = 1

    db_session.add(
        Response(
            participant_id=participant_id,
            session_question_id=question.id,
            selected_option_ids=[str(correct_option.id)],
            is_correct=True,
            is_unanswered=False,
            base_points_earned=10,
            total_points_earned=10,
            submitted_at=datetime.now(UTC),
            response_time_ms=1500,
            status="correct",
            scored_at=datetime.now(UTC),
        )
    )
    db_session.commit()

    results = client.get(
        f"/api/v1/live-rooms/{room['id']}/results",
        headers=_auth(admin_token),
    )
    assert results.status_code == 200, results.text
    data = results.json()["data"]
    assert data["room"]["id"] == room["id"]
    assert data["room"]["roomCode"] == room["roomCode"]
    assert data["summary"]["participantCount"] == 1
    assert data["summary"]["totalQuestions"] == 1
    assert data["summary"]["averageScore"] == 10
    assert data["summary"]["averageResponseTimeMs"] == 1500
    assert len(data["leaderboard"]) == 1
    assert data["leaderboard"][0]["displayName"] == "Casey"
    assert data["leaderboard"][0]["rank"] == 1
    assert len(data["podium"]["entries"]) == 1
    assert len(data["questionAnalytics"]) == 1
    qa = data["questionAnalytics"][0]
    assert qa["promptText"] == "Capital of France?"
    assert qa["sectionName"] == "Round 1"
    assert qa["submissionCount"] == 1
    assert qa["correctCount"] == 1
    assert qa["accuracyPercent"] == 100
    assert any(opt["isCorrect"] and opt["selectedCount"] == 1 for opt in qa["optionDistribution"])
    assert len(data["sectionAnalytics"]) == 1
    assert data["sectionAnalytics"][0]["averageScore"] == 10

    export = client.get(
        f"/api/v1/live-rooms/{room['id']}/results/export",
        headers=_auth(admin_token),
        params={"format": "csv"},
    )
    assert export.status_code == 200, export.text
    assert "text/csv" in export.headers["content-type"]
    lines = export.text.strip().splitlines()
    assert lines[0] == "Rank,Display Name,Email,Score,Correct,Incorrect,Unanswered,Streak"
    assert "Casey" in lines[1]
    assert "casey@example.com" in lines[1]

    xlsx = client.get(
        f"/api/v1/live-rooms/{room['id']}/results/export",
        headers=_auth(admin_token),
    )
    assert xlsx.status_code == 200, xlsx.text
    assert "spreadsheetml" in xlsx.headers["content-type"]
    assert xlsx.content[:2] == b"PK"


def test_change_password_success(client: TestClient, admin_token: str) -> None:
    new_password = "NewSecurePass1!"
    response = client.post(
        "/api/v1/admin/change-password",
        headers=_auth(admin_token),
        json={
            "currentPassword": TEST_PASSWORD,
            "newPassword": new_password,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["message"] == "Password changed successfully"

    old_login = client.post(
        "/api/v1/admin/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/v1/admin/login",
        json={"username": TEST_USERNAME, "password": new_password},
    )
    assert new_login.status_code == 200, new_login.text


def test_change_password_wrong_current(client: TestClient, admin_token: str) -> None:
    response = client.post(
        "/api/v1/admin/change-password",
        headers=_auth(admin_token),
        json={
            "currentPassword": "WrongPassw0rd!",
            "newPassword": "AnotherSecure1!",
        },
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_change_password_policy(client: TestClient, admin_token: str) -> None:
    response = client.post(
        "/api/v1/admin/change-password",
        headers=_auth(admin_token),
        json={
            "currentPassword": TEST_PASSWORD,
            "newPassword": "weakpassword",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PASSWORD_POLICY_VIOLATION"


def test_dashboard_summary(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room = _open_lobby_room(client, admin_token, db_session)
    joined = _join(
        client,
        room_code=room["roomCode"],
        display_name="Dana",
        email="dana@example.com",
    )
    assert joined.status_code == 201, joined.text

    # Ensure joined_at counts as today (UTC)
    participant = db_session.get(Participant, UUID(joined.json()["data"]["participant"]["id"]))
    assert participant is not None
    participant.joined_at = datetime.now(UTC) - timedelta(minutes=5)
    db_session.commit()

    response = client.get("/api/v1/dashboard/summary", headers=_auth(admin_token))
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["quizzesTotal"] >= 1
    assert data["quizzesInUse"] >= 1
    assert data["roomsActive"] >= 1
    assert data["participantsToday"] >= 1
    assert "roomsCompleted" in data
    assert "quizzesDraft" in data
