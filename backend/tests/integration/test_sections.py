"""Integration tests for Section CRUD (API_SPEC.md §9)."""

from uuid import uuid4

from fastapi.testclient import TestClient


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_quiz(client: TestClient, token: str, title: str = "Section Host Quiz") -> str:
    response = client.post(
        "/api/v1/quizzes",
        headers=_auth(token),
        json={"title": title},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def test_create_section(client: TestClient, admin_token: str) -> None:
    quiz_id = _create_quiz(client, admin_token)
    response = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections",
        headers=_auth(admin_token),
        json={"name": "Round 1"},
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["name"] == "Round 1"
    assert data["quizId"] == quiz_id
    assert data["sortOrder"] == 0
    assert "id" in data
    assert "createdAt" in data


def test_create_section_with_sort_order(client: TestClient, admin_token: str) -> None:
    quiz_id = _create_quiz(client, admin_token, title="Ordered Quiz")
    response = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections",
        headers=_auth(admin_token),
        json={"name": "Finals", "sortOrder": 5},
    )
    assert response.status_code == 201
    assert response.json()["data"]["sortOrder"] == 5


def test_list_sections(client: TestClient, admin_token: str) -> None:
    quiz_id = _create_quiz(client, admin_token, title="List Sections Quiz")
    client.post(
        f"/api/v1/quizzes/{quiz_id}/sections",
        headers=_auth(admin_token),
        json={"name": "A", "sortOrder": 1},
    )
    client.post(
        f"/api/v1/quizzes/{quiz_id}/sections",
        headers=_auth(admin_token),
        json={"name": "B", "sortOrder": 0},
    )
    response = client.get(
        f"/api/v1/quizzes/{quiz_id}/sections",
        headers=_auth(admin_token),
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["total"] == 2
    assert [item["name"] for item in body["items"]] == ["B", "A"]


def test_get_section(client: TestClient, admin_token: str) -> None:
    quiz_id = _create_quiz(client, admin_token, title="Get Section Quiz")
    created = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections",
        headers=_auth(admin_token),
        json={"name": "Fetch Me"},
    ).json()["data"]
    response = client.get(
        f"/api/v1/quizzes/{quiz_id}/sections/{created['id']}",
        headers=_auth(admin_token),
    )
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "Fetch Me"


def test_update_section(client: TestClient, admin_token: str) -> None:
    quiz_id = _create_quiz(client, admin_token, title="Update Section Quiz")
    created = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections",
        headers=_auth(admin_token),
        json={"name": "Old Name"},
    ).json()["data"]
    response = client.patch(
        f"/api/v1/quizzes/{quiz_id}/sections/{created['id']}",
        headers=_auth(admin_token),
        json={"name": "New Name", "sortOrder": 3},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == "New Name"
    assert data["sortOrder"] == 3


def test_delete_section(client: TestClient, admin_token: str) -> None:
    quiz_id = _create_quiz(client, admin_token, title="Delete Section Quiz")
    created = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections",
        headers=_auth(admin_token),
        json={"name": "Gone"},
    ).json()["data"]
    response = client.delete(
        f"/api/v1/quizzes/{quiz_id}/sections/{created['id']}",
        headers=_auth(admin_token),
    )
    assert response.status_code == 200
    assert response.json()["data"]["deleted"] is True

    missing = client.get(
        f"/api/v1/quizzes/{quiz_id}/sections/{created['id']}",
        headers=_auth(admin_token),
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "SECTION_NOT_FOUND"


def test_unauthorized_access(client: TestClient) -> None:
    quiz_id = uuid4()
    response = client.get(f"/api/v1/quizzes/{quiz_id}/sections")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_ERROR"


def test_invalid_payload(client: TestClient, admin_token: str) -> None:
    quiz_id = _create_quiz(client, admin_token, title="Invalid Section Payload")
    response = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections",
        headers=_auth(admin_token),
        json={},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    response = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections",
        headers=_auth(admin_token),
        json={"name": ""},
    )
    assert response.status_code == 422

    response = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections",
        headers=_auth(admin_token),
        json={"name": "Bad Order", "sortOrder": -1},
    )
    assert response.status_code == 422


def test_parent_quiz_not_found(client: TestClient, admin_token: str) -> None:
    missing_quiz = uuid4()
    response = client.post(
        f"/api/v1/quizzes/{missing_quiz}/sections",
        headers=_auth(admin_token),
        json={"name": "Orphan"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "QUIZ_NOT_FOUND"

    response = client.get(
        f"/api/v1/quizzes/{missing_quiz}/sections",
        headers=_auth(admin_token),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "QUIZ_NOT_FOUND"


def test_section_not_found(client: TestClient, admin_token: str) -> None:
    quiz_id = _create_quiz(client, admin_token, title="Missing Section Quiz")
    missing_section = uuid4()
    response = client.get(
        f"/api/v1/quizzes/{quiz_id}/sections/{missing_section}",
        headers=_auth(admin_token),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SECTION_NOT_FOUND"

    response = client.patch(
        f"/api/v1/quizzes/{quiz_id}/sections/{missing_section}",
        headers=_auth(admin_token),
        json={"name": "Nope"},
    )
    assert response.status_code == 404

    response = client.delete(
        f"/api/v1/quizzes/{quiz_id}/sections/{missing_section}",
        headers=_auth(admin_token),
    )
    assert response.status_code == 404


def test_duplicate_sort_order_rejected(client: TestClient, admin_token: str) -> None:
    quiz_id = _create_quiz(client, admin_token, title="Dup Order Quiz")
    first = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections",
        headers=_auth(admin_token),
        json={"name": "One", "sortOrder": 1},
    )
    assert first.status_code == 201
    second = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections",
        headers=_auth(admin_token),
        json={"name": "Two", "sortOrder": 1},
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "DUPLICATE_SORT_ORDER"


def test_section_wrong_quiz_not_found(client: TestClient, admin_token: str) -> None:
    quiz_a = _create_quiz(client, admin_token, title="Quiz A Sections")
    quiz_b = _create_quiz(client, admin_token, title="Quiz B Sections")
    section = client.post(
        f"/api/v1/quizzes/{quiz_a}/sections",
        headers=_auth(admin_token),
        json={"name": "Only in A"},
    ).json()["data"]
    response = client.get(
        f"/api/v1/quizzes/{quiz_b}/sections/{section['id']}",
        headers=_auth(admin_token),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SECTION_NOT_FOUND"
