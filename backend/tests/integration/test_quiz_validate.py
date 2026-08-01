"""Integration tests for quiz validate / archive / restore (quiz builder publish)."""

from fastapi.testclient import TestClient


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _build_ready_content(client: TestClient, token: str, title: str) -> str:
    quiz = client.post(
        "/api/v1/quizzes",
        headers=_auth(token),
        json={"title": title},
    ).json()["data"]
    quiz_id = quiz["id"]
    section = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections",
        headers=_auth(token),
        json={"name": "Section 1"},
    ).json()["data"]
    question = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections/{section['id']}/questions",
        headers=_auth(token),
        json={"questionType": "Text", "promptText": "Capital of France?", "basePoints": 1},
    ).json()["data"]
    for text, correct, order in (("Paris", True, 0), ("Lyon", False, 1)):
        client.post(
            f"/api/v1/quizzes/{quiz_id}/sections/{section['id']}/questions/{question['id']}/options",
            headers=_auth(token),
            json={"text": text, "isCorrect": correct, "sortOrder": order},
        )
    return quiz_id


def test_validate_promotes_to_ready(client: TestClient, admin_token: str) -> None:
    quiz_id = _build_ready_content(client, admin_token, "Publish Me")
    response = client.post(
        f"/api/v1/quizzes/{quiz_id}/validate",
        headers=_auth(admin_token),
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "Ready"


def test_validate_rejects_incomplete_quiz(client: TestClient, admin_token: str) -> None:
    quiz = client.post(
        "/api/v1/quizzes",
        headers=_auth(admin_token),
        json={"title": "Empty Draft"},
    ).json()["data"]
    response = client.post(
        f"/api/v1/quizzes/{quiz['id']}/validate",
        headers=_auth(admin_token),
    )
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "QUIZ_NOT_READY"
    assert body["details"]


def test_archive_and_restore(client: TestClient, admin_token: str) -> None:
    quiz_id = _build_ready_content(client, admin_token, "Archive Me")
    assert (
        client.post(f"/api/v1/quizzes/{quiz_id}/validate", headers=_auth(admin_token)).status_code
        == 200
    )
    archived = client.post(f"/api/v1/quizzes/{quiz_id}/archive", headers=_auth(admin_token))
    assert archived.status_code == 200
    assert archived.json()["data"]["status"] == "Archived"
    restored = client.post(f"/api/v1/quizzes/{quiz_id}/restore", headers=_auth(admin_token))
    assert restored.status_code == 200
    assert restored.json()["data"]["status"] == "Ready"
