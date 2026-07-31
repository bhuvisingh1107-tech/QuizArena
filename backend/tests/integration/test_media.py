"""Integration tests for Media Management (API_SPEC.md §10)."""

from io import BytesIO
from uuid import uuid4

from fastapi.testclient import TestClient

# Minimal magic-byte payloads accepted by FileStorageService.detect_mime_type
JPEG_BYTES = b"\xff\xd8\xff" + b"\x00" * 64
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
MP3_BYTES = b"ID3" + b"\x00" * 64
WAV_BYTES = b"RIFF" + (64).to_bytes(4, "little") + b"WAVE" + b"\x00" * 56
TEXT_BYTES = b"not a media file at all"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _upload(
    client: TestClient,
    token: str,
    *,
    data: bytes,
    filename: str,
    category: str,
    content_type: str,
    quiz_id: str | None = None,
):
    form: dict = {"category": category}
    if quiz_id is not None:
        form["quizId"] = quiz_id
    return client.post(
        "/api/v1/media",
        headers=_auth(token),
        data=form,
        files={"file": (filename, BytesIO(data), content_type)},
    )


def _setup_image_question(client: TestClient, token: str) -> tuple[str, str, str]:
    quiz = client.post(
        "/api/v1/quizzes",
        headers=_auth(token),
        json={"title": "Media Host Quiz"},
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
        json={"questionType": "Image", "promptText": "What is shown?"},
    )
    assert question.status_code == 201, question.text
    return quiz_id, section_id, question.json()["data"]["id"]


def test_upload_image(client: TestClient, admin_token: str) -> None:
    response = _upload(
        client,
        admin_token,
        data=JPEG_BYTES,
        filename="photo.jpg",
        category="question_image",
        content_type="image/jpeg",
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["category"] == "question_image"
    assert data["mimeType"] == "image/jpeg"
    assert data["fileSize"] == len(JPEG_BYTES)
    assert data["originalFilename"] == "photo.jpg"
    assert data["url"] == f"/api/v1/media/{data['id']}/content"


def test_upload_audio(client: TestClient, admin_token: str) -> None:
    response = _upload(
        client,
        admin_token,
        data=MP3_BYTES,
        filename="clip.mp3",
        category="question_audio",
        content_type="audio/mpeg",
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["category"] == "question_audio"
    assert data["mimeType"] == "audio/mpeg"


def test_upload_wav(client: TestClient, admin_token: str) -> None:
    response = _upload(
        client,
        admin_token,
        data=WAV_BYTES,
        filename="clip.wav",
        category="question_audio",
        content_type="audio/wav",
    )
    assert response.status_code == 201, response.text
    assert response.json()["data"]["mimeType"] == "audio/wav"


def test_invalid_file_type(client: TestClient, admin_token: str) -> None:
    response = _upload(
        client,
        admin_token,
        data=TEXT_BYTES,
        filename="notes.txt",
        category="question_image",
        content_type="text/plain",
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_audio_rejected_as_image(client: TestClient, admin_token: str) -> None:
    response = _upload(
        client,
        admin_token,
        data=MP3_BYTES,
        filename="clip.mp3",
        category="question_image",
        content_type="audio/mpeg",
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_file_too_large(client: TestClient, admin_token: str) -> None:
    # Question image limit is 5 MB
    oversized = b"\xff\xd8\xff" + b"\x00" * (5 * 1024 * 1024)
    response = _upload(
        client,
        admin_token,
        data=oversized,
        filename="huge.jpg",
        category="question_image",
        content_type="image/jpeg",
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_missing_file(client: TestClient, admin_token: str) -> None:
    response = client.post(
        "/api/v1/media",
        headers=_auth(admin_token),
        data={"category": "question_image"},
    )
    assert response.status_code == 422


def test_get_media(client: TestClient, admin_token: str) -> None:
    created = _upload(
        client,
        admin_token,
        data=PNG_BYTES,
        filename="pic.png",
        category="question_image",
        content_type="image/png",
    ).json()["data"]

    response = client.get(
        f"/api/v1/media/{created['id']}",
        headers=_auth(admin_token),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == created["id"]
    assert data["mimeType"] == "image/png"

    content = client.get(
        f"/api/v1/media/{created['id']}/content",
        headers=_auth(admin_token),
    )
    assert content.status_code == 200
    assert content.content == PNG_BYTES
    assert content.headers["content-type"].startswith("image/png")


def test_get_media_not_found(client: TestClient, admin_token: str) -> None:
    response = client.get(
        f"/api/v1/media/{uuid4()}",
        headers=_auth(admin_token),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "MEDIA_NOT_FOUND"


def test_delete_media(client: TestClient, admin_token: str) -> None:
    created = _upload(
        client,
        admin_token,
        data=JPEG_BYTES,
        filename="delete-me.jpg",
        category="question_image",
        content_type="image/jpeg",
    ).json()["data"]

    response = client.delete(
        f"/api/v1/media/{created['id']}",
        headers=_auth(admin_token),
    )
    assert response.status_code == 200
    assert response.json()["data"]["deleted"] is True

    missing = client.get(
        f"/api/v1/media/{created['id']}",
        headers=_auth(admin_token),
    )
    assert missing.status_code == 404


def test_unauthorized(client: TestClient) -> None:
    response = client.get(f"/api/v1/media/{uuid4()}")
    assert response.status_code == 401

    response = client.post(
        "/api/v1/media",
        data={"category": "question_image"},
        files={"file": ("x.jpg", BytesIO(JPEG_BYTES), "image/jpeg")},
    )
    assert response.status_code == 401


def test_attach_media_to_question(client: TestClient, admin_token: str) -> None:
    quiz_id, section_id, question_id = _setup_image_question(client, admin_token)
    media = _upload(
        client,
        admin_token,
        data=JPEG_BYTES,
        filename="prompt.jpg",
        category="question_image",
        content_type="image/jpeg",
    ).json()["data"]

    response = client.post(
        f"/api/v1/media/{media['id']}/attach",
        headers=_auth(admin_token),
        json={
            "quizId": quiz_id,
            "sectionId": section_id,
            "questionId": question_id,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["mediaFileId"] == media["id"]
    assert body["questionId"] == question_id

    question = client.get(
        f"/api/v1/quizzes/{quiz_id}/sections/{section_id}/questions/{question_id}",
        headers=_auth(admin_token),
    )
    assert question.status_code == 200
    assert question.json()["data"]["mediaFileId"] == media["id"]

    # Referenced media cannot be deleted
    blocked = client.delete(
        f"/api/v1/media/{media['id']}",
        headers=_auth(admin_token),
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "MEDIA_IN_USE"


def test_attach_media_type_mismatch(client: TestClient, admin_token: str) -> None:
    quiz_id, section_id, question_id = _setup_image_question(client, admin_token)
    audio = _upload(
        client,
        admin_token,
        data=MP3_BYTES,
        filename="clip.mp3",
        category="question_audio",
        content_type="audio/mpeg",
    ).json()["data"]

    response = client.post(
        f"/api/v1/media/{audio['id']}/attach",
        headers=_auth(admin_token),
        json={
            "quizId": quiz_id,
            "sectionId": section_id,
            "questionId": question_id,
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "MEDIA_TYPE_MISMATCH"


def test_attach_invalid_question(client: TestClient, admin_token: str) -> None:
    media = _upload(
        client,
        admin_token,
        data=JPEG_BYTES,
        filename="orphan.jpg",
        category="question_image",
        content_type="image/jpeg",
    ).json()["data"]

    response = client.post(
        f"/api/v1/media/{media['id']}/attach",
        headers=_auth(admin_token),
        json={
            "quizId": str(uuid4()),
            "sectionId": str(uuid4()),
            "questionId": str(uuid4()),
        },
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "QUIZ_NOT_FOUND"
