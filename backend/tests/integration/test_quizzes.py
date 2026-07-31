"""Integration tests for Quiz CRUD (API_SPEC.md §8)."""

from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import QuizStatus
from app.models.quiz import Quiz


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _set_status(db_session: Session, quiz_id: str, status: QuizStatus) -> None:
    quiz = db_session.get(Quiz, UUID(quiz_id))
    assert quiz is not None
    quiz.status = status
    db_session.commit()


def test_create_quiz(client: TestClient, admin_token: str) -> None:
    response = client.post(
        "/api/v1/quizzes",
        headers=_auth(admin_token),
        json={"title": "Geography Bee", "description": "World capitals"},
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["title"] == "Geography Bee"
    assert data["description"] == "World capitals"
    assert data["status"] == "Draft"
    assert data["config"]["questionAdvanceMode"] == "manual"
    assert data["config"]["answerRevealBehavior"] == "after_each"
    assert "id" in data
    assert "createdAt" in data


def test_create_quiz_with_config(client: TestClient, admin_token: str) -> None:
    response = client.post(
        "/api/v1/quizzes",
        headers=_auth(admin_token),
        json={
            "title": "Science Round",
            "config": {
                "questionAdvanceMode": "automatic",
                "timeBonusEnabled": True,
                "timeBonusMaxPoints": 50,
            },
        },
    )
    assert response.status_code == 201
    config = response.json()["data"]["config"]
    assert config["questionAdvanceMode"] == "automatic"
    assert config["timeBonusEnabled"] is True
    assert config["timeBonusMaxPoints"] == 50


def test_list_quizzes(client: TestClient, admin_token: str) -> None:
    client.post(
        "/api/v1/quizzes",
        headers=_auth(admin_token),
        json={"title": "Quiz A"},
    )
    client.post(
        "/api/v1/quizzes",
        headers=_auth(admin_token),
        json={"title": "Quiz B"},
    )
    response = client.get("/api/v1/quizzes", headers=_auth(admin_token))
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["total"] >= 2
    assert len(body["data"]["items"]) >= 2
    assert "hasMore" in body["meta"]


def test_list_quizzes_search(client: TestClient, admin_token: str) -> None:
    client.post(
        "/api/v1/quizzes",
        headers=_auth(admin_token),
        json={"title": "UniqueSearchTitleXYZ"},
    )
    response = client.get(
        "/api/v1/quizzes",
        headers=_auth(admin_token),
        params={"search": "UniqueSearchTitleXYZ"},
    )
    assert response.status_code == 200
    items = response.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["title"] == "UniqueSearchTitleXYZ"


def test_get_quiz(client: TestClient, admin_token: str) -> None:
    created = client.post(
        "/api/v1/quizzes",
        headers=_auth(admin_token),
        json={"title": "Fetch Me"},
    ).json()["data"]
    response = client.get(
        f"/api/v1/quizzes/{created['id']}",
        headers=_auth(admin_token),
    )
    assert response.status_code == 200
    assert response.json()["data"]["id"] == created["id"]
    assert response.json()["data"]["title"] == "Fetch Me"


def test_update_quiz(client: TestClient, admin_token: str) -> None:
    created = client.post(
        "/api/v1/quizzes",
        headers=_auth(admin_token),
        json={"title": "Old Title"},
    ).json()["data"]
    response = client.patch(
        f"/api/v1/quizzes/{created['id']}",
        headers=_auth(admin_token),
        json={"title": "New Title", "description": "Updated"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["title"] == "New Title"
    assert data["description"] == "Updated"
    assert data["status"] == "Draft"


def test_delete_quiz_soft(client: TestClient, admin_token: str) -> None:
    created = client.post(
        "/api/v1/quizzes",
        headers=_auth(admin_token),
        json={"title": "To Delete"},
    ).json()["data"]
    response = client.delete(
        f"/api/v1/quizzes/{created['id']}",
        headers=_auth(admin_token),
    )
    assert response.status_code == 200
    assert response.json()["data"]["deleted"] is True
    assert response.json()["data"]["hard"] is False
    assert response.json()["data"]["status"] == "Deleted"

    missing = client.get(
        f"/api/v1/quizzes/{created['id']}",
        headers=_auth(admin_token),
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "QUIZ_NOT_FOUND"

    # Soft-deleted quizzes are excluded from the default list
    listed = client.get("/api/v1/quizzes", headers=_auth(admin_token))
    ids = {item["id"] for item in listed.json()["data"]["items"]}
    assert created["id"] not in ids


def test_delete_quiz_hard(client: TestClient, admin_token: str) -> None:
    created = client.post(
        "/api/v1/quizzes",
        headers=_auth(admin_token),
        json={"title": "Hard Delete Me"},
    ).json()["data"]
    response = client.delete(
        f"/api/v1/quizzes/{created['id']}",
        headers=_auth(admin_token),
        params={"hard": True},
    )
    assert response.status_code == 200
    assert response.json()["data"]["hard"] is True


def test_unauthorized_access(client: TestClient) -> None:
    response = client.get("/api/v1/quizzes")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_ERROR"

    response = client.post("/api/v1/quizzes", json={"title": "Nope"})
    assert response.status_code == 401


def test_invalid_payload(client: TestClient, admin_token: str) -> None:
    response = client.post(
        "/api/v1/quizzes",
        headers=_auth(admin_token),
        json={},  # missing title
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    response = client.post(
        "/api/v1/quizzes",
        headers=_auth(admin_token),
        json={"title": ""},
    )
    assert response.status_code == 422

    response = client.post(
        "/api/v1/quizzes",
        headers=_auth(admin_token),
        json={"title": "Bad Config", "config": {"questionAdvanceMode": "not-a-mode"}},
    )
    assert response.status_code == 422


def test_quiz_not_found(client: TestClient, admin_token: str) -> None:
    missing_id = uuid4()
    response = client.get(
        f"/api/v1/quizzes/{missing_id}",
        headers=_auth(admin_token),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "QUIZ_NOT_FOUND"

    response = client.patch(
        f"/api/v1/quizzes/{missing_id}",
        headers=_auth(admin_token),
        json={"title": "Ghost"},
    )
    assert response.status_code == 404

    response = client.delete(
        f"/api/v1/quizzes/{missing_id}",
        headers=_auth(admin_token),
    )
    assert response.status_code == 404


def test_cannot_delete_in_use_quiz(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    created = client.post(
        "/api/v1/quizzes",
        headers=_auth(admin_token),
        json={"title": "Live Quiz"},
    ).json()["data"]
    _set_status(db_session, created["id"], QuizStatus.IN_USE)

    response = client.delete(
        f"/api/v1/quizzes/{created['id']}",
        headers=_auth(admin_token),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "QUIZ_IN_USE"


def test_cannot_edit_archived_quiz(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    created = client.post(
        "/api/v1/quizzes",
        headers=_auth(admin_token),
        json={"title": "Archive Candidate"},
    ).json()["data"]
    _set_status(db_session, created["id"], QuizStatus.ARCHIVED)

    response = client.patch(
        f"/api/v1/quizzes/{created['id']}",
        headers=_auth(admin_token),
        json={"title": "Should Fail"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "QUIZ_NOT_EDITABLE"


def test_ready_falls_back_to_draft_on_edit_without_sections(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    created = client.post(
        "/api/v1/quizzes",
        headers=_auth(admin_token),
        json={"title": "Almost Ready"},
    ).json()["data"]
    _set_status(db_session, created["id"], QuizStatus.READY)

    response = client.patch(
        f"/api/v1/quizzes/{created['id']}",
        headers=_auth(admin_token),
        json={"description": "Still no sections"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "Draft"
