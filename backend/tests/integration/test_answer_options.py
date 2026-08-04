"""Integration tests for Answer Option CRUD (API_SPEC.md §9)."""

from uuid import uuid4

from fastapi.testclient import TestClient


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _setup(
    client: TestClient,
    token: str,
    *,
    allow_multiple_correct: bool = False,
    quiz_title: str = "Option Host Quiz",
) -> tuple[str, str, str]:
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
        json={"name": "Round 1"},
    )
    assert section.status_code == 201, section.text
    section_id = section.json()["data"]["id"]

    question = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections/{section_id}/questions",
        headers=_auth(token),
        json={
            "questionType": "Text",
            "promptText": "Pick one",
            "allowMultipleCorrect": allow_multiple_correct,
        },
    )
    assert question.status_code == 201, question.text
    return quiz_id, section_id, question.json()["data"]["id"]


def _opath(
    quiz_id: str,
    section_id: str,
    question_id: str,
    option_id: str | None = None,
) -> str:
    base = (
        f"/api/v1/quizzes/{quiz_id}/sections/{section_id}"
        f"/questions/{question_id}/options"
    )
    return f"{base}/{option_id}" if option_id else base


def test_create_option(client: TestClient, admin_token: str) -> None:
    quiz_id, section_id, question_id = _setup(client, admin_token)
    response = client.post(
        _opath(quiz_id, section_id, question_id),
        headers=_auth(admin_token),
        json={"text": "Paris", "isCorrect": True},
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["text"] == "Paris"
    assert data["isCorrect"] is True
    assert data["questionId"] == question_id
    assert data["sortOrder"] == 0


def test_list_options(client: TestClient, admin_token: str) -> None:
    quiz_id, section_id, question_id = _setup(
        client, admin_token, quiz_title="List Options Quiz"
    )
    client.post(
        _opath(quiz_id, section_id, question_id),
        headers=_auth(admin_token),
        json={"text": "B", "sortOrder": 1},
    )
    client.post(
        _opath(quiz_id, section_id, question_id),
        headers=_auth(admin_token),
        json={"text": "A", "sortOrder": 0},
    )
    response = client.get(
        _opath(quiz_id, section_id, question_id),
        headers=_auth(admin_token),
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["total"] == 2
    assert [item["text"] for item in body["items"]] == ["A", "B"]


def test_get_option(client: TestClient, admin_token: str) -> None:
    quiz_id, section_id, question_id = _setup(
        client, admin_token, quiz_title="Get Option Quiz"
    )
    created = client.post(
        _opath(quiz_id, section_id, question_id),
        headers=_auth(admin_token),
        json={"text": "Fetch me"},
    ).json()["data"]
    response = client.get(
        _opath(quiz_id, section_id, question_id, created["id"]),
        headers=_auth(admin_token),
    )
    assert response.status_code == 200
    assert response.json()["data"]["text"] == "Fetch me"


def test_update_option(client: TestClient, admin_token: str) -> None:
    quiz_id, section_id, question_id = _setup(
        client, admin_token, quiz_title="Update Option Quiz"
    )
    created = client.post(
        _opath(quiz_id, section_id, question_id),
        headers=_auth(admin_token),
        json={"text": "Old"},
    ).json()["data"]
    response = client.patch(
        _opath(quiz_id, section_id, question_id, created["id"]),
        headers=_auth(admin_token),
        json={"text": "New", "isCorrect": True, "sortOrder": 2},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["text"] == "New"
    assert data["isCorrect"] is True
    assert data["sortOrder"] == 2


def test_delete_option(client: TestClient, admin_token: str) -> None:
    quiz_id, section_id, question_id = _setup(
        client, admin_token, quiz_title="Delete Option Quiz"
    )
    created = client.post(
        _opath(quiz_id, section_id, question_id),
        headers=_auth(admin_token),
        json={"text": "Gone"},
    ).json()["data"]
    response = client.delete(
        _opath(quiz_id, section_id, question_id, created["id"]),
        headers=_auth(admin_token),
    )
    assert response.status_code == 200
    assert response.json()["data"]["deleted"] is True

    missing = client.get(
        _opath(quiz_id, section_id, question_id, created["id"]),
        headers=_auth(admin_token),
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "ANSWER_OPTION_NOT_FOUND"


def test_unauthorized(client: TestClient) -> None:
    response = client.get(
        f"/api/v1/quizzes/{uuid4()}/sections/{uuid4()}/questions/{uuid4()}/options",
    )
    assert response.status_code == 401


def test_invalid_payload(client: TestClient, admin_token: str) -> None:
    quiz_id, section_id, question_id = _setup(
        client, admin_token, quiz_title="Invalid Option Payload"
    )
    response = client.post(
        _opath(quiz_id, section_id, question_id),
        headers=_auth(admin_token),
        json={},
    )
    assert response.status_code == 422

    response = client.post(
        _opath(quiz_id, section_id, question_id),
        headers=_auth(admin_token),
        json={"text": ""},
    )
    assert response.status_code == 422

    response = client.post(
        _opath(quiz_id, section_id, question_id),
        headers=_auth(admin_token),
        json={"text": "Bad", "sortOrder": -1},
    )
    assert response.status_code == 422


def test_missing_parents(client: TestClient, admin_token: str) -> None:
    response = client.post(
        f"/api/v1/quizzes/{uuid4()}/sections/{uuid4()}/questions/{uuid4()}/options",
        headers=_auth(admin_token),
        json={"text": "Orphan"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "QUIZ_NOT_FOUND"

    quiz = client.post(
        "/api/v1/quizzes",
        headers=_auth(admin_token),
        json={"title": "Missing Section Options"},
    ).json()["data"]
    response = client.post(
        f"/api/v1/quizzes/{quiz['id']}/sections/{uuid4()}/questions/{uuid4()}/options",
        headers=_auth(admin_token),
        json={"text": "No section"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SECTION_NOT_FOUND"

    quiz_id, section_id, _ = _setup(client, admin_token, quiz_title="Missing Q Options")
    response = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections/{section_id}/questions/{uuid4()}/options",
        headers=_auth(admin_token),
        json={"text": "No question"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "QUESTION_NOT_FOUND"


def test_wrong_parent_relationships(client: TestClient, admin_token: str) -> None:
    quiz_id, section_id, question_a = _setup(
        client, admin_token, quiz_title="Wrong Rel Options"
    )
    question_b = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections/{section_id}/questions",
        headers=_auth(admin_token),
        json={"questionType": "Text", "promptText": "Other Q", "sortOrder": 1},
    ).json()["data"]["id"]
    option = client.post(
        _opath(quiz_id, section_id, question_a),
        headers=_auth(admin_token),
        json={"text": "Only on A"},
    ).json()["data"]

    response = client.get(
        _opath(quiz_id, section_id, question_b, option["id"]),
        headers=_auth(admin_token),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ANSWER_OPTION_NOT_FOUND"


def test_duplicate_sort_order(client: TestClient, admin_token: str) -> None:
    quiz_id, section_id, question_id = _setup(
        client, admin_token, quiz_title="Dup Sort Options"
    )
    first = client.post(
        _opath(quiz_id, section_id, question_id),
        headers=_auth(admin_token),
        json={"text": "One", "sortOrder": 1},
    )
    assert first.status_code == 201
    second = client.post(
        _opath(quiz_id, section_id, question_id),
        headers=_auth(admin_token),
        json={"text": "Two", "sortOrder": 1},
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "DUPLICATE_SORT_ORDER"


def test_single_correct_violation(client: TestClient, admin_token: str) -> None:
    quiz_id, section_id, question_id = _setup(
        client,
        admin_token,
        allow_multiple_correct=False,
        quiz_title="Single Correct Quiz",
    )
    first = client.post(
        _opath(quiz_id, section_id, question_id),
        headers=_auth(admin_token),
        json={"text": "Correct", "isCorrect": True},
    )
    assert first.status_code == 201
    second = client.post(
        _opath(quiz_id, section_id, question_id),
        headers=_auth(admin_token),
        json={"text": "Also correct?", "isCorrect": True},
    )
    assert second.status_code == 400
    assert second.json()["error"]["code"] == "MCQ_INVALID"


def test_multiple_correct_rejected(client: TestClient, admin_token: str) -> None:
    """Even allowMultipleCorrect=true is rejected — MCQs require exactly one correct."""
    quiz_id, section_id, question_id = _setup(
        client,
        admin_token,
        allow_multiple_correct=True,
        quiz_title="Multi Correct Quiz",
    )
    first = client.post(
        _opath(quiz_id, section_id, question_id),
        headers=_auth(admin_token),
        json={"text": "A", "isCorrect": True},
    )
    second = client.post(
        _opath(quiz_id, section_id, question_id),
        headers=_auth(admin_token),
        json={"text": "B", "isCorrect": True, "sortOrder": 1},
    )
    assert first.status_code == 201
    assert second.status_code == 400
    assert second.json()["error"]["code"] == "MCQ_INVALID"


def test_option_limit(client: TestClient, admin_token: str) -> None:
    quiz_id, section_id, question_id = _setup(
        client, admin_token, quiz_title="Option Limit Quiz"
    )
    for i in range(4):
        response = client.post(
            _opath(quiz_id, section_id, question_id),
            headers=_auth(admin_token),
            json={"text": f"Opt {i}", "sortOrder": i, "isCorrect": i == 0},
        )
        assert response.status_code == 201, response.text
    overflow = client.post(
        _opath(quiz_id, section_id, question_id),
        headers=_auth(admin_token),
        json={"text": "Too many", "sortOrder": 4},
    )
    assert overflow.status_code == 400
    assert overflow.json()["error"]["code"] == "MCQ_INVALID"
