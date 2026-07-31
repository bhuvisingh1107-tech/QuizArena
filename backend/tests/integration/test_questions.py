"""Integration tests for Question CRUD (API_SPEC.md §9)."""

from uuid import uuid4

from fastapi.testclient import TestClient


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_quiz_and_section(
    client: TestClient,
    token: str,
    *,
    quiz_title: str = "Question Host Quiz",
    section_name: str = "Round 1",
) -> tuple[str, str]:
    quiz = client.post(
        "/api/v1/quizzes",
        headers=_auth(token),
        json={"title": quiz_title},
    )
    assert quiz.status_code == 201, quiz.text
    quiz_id = quiz.json()["data"]["id"]

    section = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections",
        headers=_auth(token),
        json={"name": section_name},
    )
    assert section.status_code == 201, section.text
    return quiz_id, section.json()["data"]["id"]


def _qpath(quiz_id: str, section_id: str, question_id: str | None = None) -> str:
    base = f"/api/v1/quizzes/{quiz_id}/sections/{section_id}/questions"
    return f"{base}/{question_id}" if question_id else base


def test_create_question(client: TestClient, admin_token: str) -> None:
    quiz_id, section_id = _create_quiz_and_section(client, admin_token)
    response = client.post(
        _qpath(quiz_id, section_id),
        headers=_auth(admin_token),
        json={
            "questionType": "Text",
            "promptText": "What is the capital of France?",
            "basePoints": 10,
        },
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["promptText"] == "What is the capital of France?"
    assert data["questionType"] == "Text"
    assert data["basePoints"] == 10
    assert data["sectionId"] == section_id
    assert data["sortOrder"] == 0
    assert data["allowMultipleCorrect"] is False


def test_list_questions(client: TestClient, admin_token: str) -> None:
    quiz_id, section_id = _create_quiz_and_section(
        client, admin_token, quiz_title="List Q Quiz"
    )
    client.post(
        _qpath(quiz_id, section_id),
        headers=_auth(admin_token),
        json={"questionType": "Text", "promptText": "Q1", "sortOrder": 1},
    )
    client.post(
        _qpath(quiz_id, section_id),
        headers=_auth(admin_token),
        json={"questionType": "Text", "promptText": "Q0", "sortOrder": 0},
    )
    response = client.get(_qpath(quiz_id, section_id), headers=_auth(admin_token))
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["total"] == 2
    assert [item["promptText"] for item in body["items"]] == ["Q0", "Q1"]


def test_get_question(client: TestClient, admin_token: str) -> None:
    quiz_id, section_id = _create_quiz_and_section(
        client, admin_token, quiz_title="Get Q Quiz"
    )
    created = client.post(
        _qpath(quiz_id, section_id),
        headers=_auth(admin_token),
        json={"questionType": "Buzzer", "promptText": "Buzz me"},
    ).json()["data"]
    response = client.get(
        _qpath(quiz_id, section_id, created["id"]),
        headers=_auth(admin_token),
    )
    assert response.status_code == 200
    assert response.json()["data"]["questionType"] == "Buzzer"


def test_update_question(client: TestClient, admin_token: str) -> None:
    quiz_id, section_id = _create_quiz_and_section(
        client, admin_token, quiz_title="Update Q Quiz"
    )
    created = client.post(
        _qpath(quiz_id, section_id),
        headers=_auth(admin_token),
        json={"questionType": "Text", "promptText": "Old"},
    ).json()["data"]
    response = client.patch(
        _qpath(quiz_id, section_id, created["id"]),
        headers=_auth(admin_token),
        json={
            "promptText": "New prompt",
            "basePoints": 25,
            "timeLimitSeconds": 30,
            "sortOrder": 2,
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["promptText"] == "New prompt"
    assert data["basePoints"] == 25
    assert data["timeLimitSeconds"] == 30
    assert data["sortOrder"] == 2


def test_delete_question(client: TestClient, admin_token: str) -> None:
    quiz_id, section_id = _create_quiz_and_section(
        client, admin_token, quiz_title="Delete Q Quiz"
    )
    created = client.post(
        _qpath(quiz_id, section_id),
        headers=_auth(admin_token),
        json={"questionType": "Text", "promptText": "Remove me"},
    ).json()["data"]
    response = client.delete(
        _qpath(quiz_id, section_id, created["id"]),
        headers=_auth(admin_token),
    )
    assert response.status_code == 200
    assert response.json()["data"]["deleted"] is True

    missing = client.get(
        _qpath(quiz_id, section_id, created["id"]),
        headers=_auth(admin_token),
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "QUESTION_NOT_FOUND"


def test_unauthorized(client: TestClient) -> None:
    response = client.get(
        f"/api/v1/quizzes/{uuid4()}/sections/{uuid4()}/questions",
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_ERROR"


def test_invalid_payload(client: TestClient, admin_token: str) -> None:
    quiz_id, section_id = _create_quiz_and_section(
        client, admin_token, quiz_title="Invalid Q Payload"
    )
    response = client.post(
        _qpath(quiz_id, section_id),
        headers=_auth(admin_token),
        json={},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    response = client.post(
        _qpath(quiz_id, section_id),
        headers=_auth(admin_token),
        json={"questionType": "Text", "promptText": ""},
    )
    assert response.status_code == 422

    response = client.post(
        _qpath(quiz_id, section_id),
        headers=_auth(admin_token),
        json={"questionType": "NotAType", "promptText": "Hi"},
    )
    assert response.status_code == 422

    response = client.post(
        _qpath(quiz_id, section_id),
        headers=_auth(admin_token),
        json={"questionType": "Text", "promptText": "Hi", "basePoints": 0},
    )
    assert response.status_code == 422


def test_parent_quiz_missing(client: TestClient, admin_token: str) -> None:
    response = client.post(
        f"/api/v1/quizzes/{uuid4()}/sections/{uuid4()}/questions",
        headers=_auth(admin_token),
        json={"questionType": "Text", "promptText": "Orphan"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "QUIZ_NOT_FOUND"


def test_parent_section_missing(client: TestClient, admin_token: str) -> None:
    quiz = client.post(
        "/api/v1/quizzes",
        headers=_auth(admin_token),
        json={"title": "No Section Quiz"},
    ).json()["data"]
    response = client.post(
        f"/api/v1/quizzes/{quiz['id']}/sections/{uuid4()}/questions",
        headers=_auth(admin_token),
        json={"questionType": "Text", "promptText": "No section"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SECTION_NOT_FOUND"


def test_wrong_section_relationship(client: TestClient, admin_token: str) -> None:
    quiz_id, section_a = _create_quiz_and_section(
        client, admin_token, quiz_title="Rel Quiz", section_name="A"
    )
    section_b = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections",
        headers=_auth(admin_token),
        json={"name": "B", "sortOrder": 1},
    ).json()["data"]["id"]
    question = client.post(
        _qpath(quiz_id, section_a),
        headers=_auth(admin_token),
        json={"questionType": "Text", "promptText": "Only in A"},
    ).json()["data"]

    response = client.get(
        _qpath(quiz_id, section_b, question["id"]),
        headers=_auth(admin_token),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "QUESTION_NOT_FOUND"


def test_invalid_uuid(client: TestClient, admin_token: str) -> None:
    response = client.get(
        "/api/v1/quizzes/not-a-uuid/sections/also-bad/questions",
        headers=_auth(admin_token),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_duplicate_sort_order(client: TestClient, admin_token: str) -> None:
    quiz_id, section_id = _create_quiz_and_section(
        client, admin_token, quiz_title="Dup Sort Q"
    )
    first = client.post(
        _qpath(quiz_id, section_id),
        headers=_auth(admin_token),
        json={"questionType": "Text", "promptText": "One", "sortOrder": 1},
    )
    assert first.status_code == 201
    second = client.post(
        _qpath(quiz_id, section_id),
        headers=_auth(admin_token),
        json={"questionType": "Text", "promptText": "Two", "sortOrder": 1},
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "DUPLICATE_SORT_ORDER"
