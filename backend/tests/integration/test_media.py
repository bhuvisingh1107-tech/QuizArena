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


def _create_quiz_with_questions(
    client: TestClient,
    token: str,
    *,
    section_count: int = 2,
    questions_per_section: int = 2,
    question_type: str = "Text",
) -> tuple[str, list[tuple[str, str]]]:
    """Return quiz_id and list of (section_id, question_id)."""
    quiz = client.post(
        "/api/v1/quizzes",
        headers=_auth(token),
        json={"title": "Bulk Media Quiz"},
    )
    assert quiz.status_code == 201, quiz.text
    quiz_id = quiz.json()["data"]["id"]
    pairs: list[tuple[str, str]] = []
    for s in range(section_count):
        section = client.post(
            f"/api/v1/quizzes/{quiz_id}/sections",
            headers=_auth(token),
            json={"name": f"Section {s + 1}"},
        )
        assert section.status_code == 201, section.text
        section_id = section.json()["data"]["id"]
        for q in range(questions_per_section):
            question = client.post(
                f"/api/v1/quizzes/{quiz_id}/sections/{section_id}/questions",
                headers=_auth(token),
                json={
                    "questionType": question_type,
                    "promptText": f"Q{s + 1}-{q + 1}?",
                },
            )
            assert question.status_code == 201, question.text
            pairs.append((section_id, question.json()["data"]["id"]))
    return quiz_id, pairs


def test_apply_image_to_all_questions(client: TestClient, admin_token: str) -> None:
    quiz_id, pairs = _create_quiz_with_questions(client, admin_token)
    assert len(pairs) == 4

    media = _upload(
        client,
        admin_token,
        data=JPEG_BYTES,
        filename="shared.jpg",
        category="question_image",
        content_type="image/jpeg",
        quiz_id=quiz_id,
    ).json()["data"]

    first_section, first_question = pairs[0]
    attach = client.post(
        f"/api/v1/media/{media['id']}/attach",
        headers=_auth(admin_token),
        json={
            "quizId": quiz_id,
            "sectionId": first_section,
            "questionId": first_question,
        },
    )
    assert attach.status_code == 200, attach.text

    response = client.post(
        f"/api/v1/media/{media['id']}/apply-to-all",
        headers=_auth(admin_token),
        json={"quizId": quiz_id},
    )
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["mediaFileId"] == media["id"]
    assert body["updatedCount"] == 4
    assert body["skippedCount"] == 0
    assert len(body["questionIds"]) == 4

    for section_id, question_id in pairs:
        question = client.get(
            f"/api/v1/quizzes/{quiz_id}/sections/{section_id}/questions/{question_id}",
            headers=_auth(admin_token),
        )
        assert question.status_code == 200
        assert question.json()["data"]["mediaFileId"] == media["id"]

    listed = client.get(
        f"/api/v1/media?quizId={quiz_id}",
        headers=_auth(admin_token),
    )
    assert listed.status_code == 200
    items = listed.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["id"] == media["id"]


def test_apply_image_replaces_existing_images(client: TestClient, admin_token: str) -> None:
    quiz_id, pairs = _create_quiz_with_questions(
        client, admin_token, section_count=1, questions_per_section=2, question_type="Image"
    )
    section_id = pairs[0][0]

    old_media = _upload(
        client,
        admin_token,
        data=PNG_BYTES,
        filename="old.png",
        category="question_image",
        content_type="image/png",
        quiz_id=quiz_id,
    ).json()["data"]
    new_media = _upload(
        client,
        admin_token,
        data=JPEG_BYTES,
        filename="new.jpg",
        category="question_image",
        content_type="image/jpeg",
        quiz_id=quiz_id,
    ).json()["data"]

    for _, question_id in pairs:
        attached = client.post(
            f"/api/v1/media/{old_media['id']}/attach",
            headers=_auth(admin_token),
            json={
                "quizId": quiz_id,
                "sectionId": section_id,
                "questionId": question_id,
            },
        )
        assert attached.status_code == 200, attached.text

    response = client.post(
        f"/api/v1/media/{new_media['id']}/apply-to-all",
        headers=_auth(admin_token),
        json={"quizId": quiz_id},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["updatedCount"] == 2

    for _, question_id in pairs:
        question = client.get(
            f"/api/v1/quizzes/{quiz_id}/sections/{section_id}/questions/{question_id}",
            headers=_auth(admin_token),
        )
        assert question.json()["data"]["mediaFileId"] == new_media["id"]

    old_get = client.get(
        f"/api/v1/media/{old_media['id']}",
        headers=_auth(admin_token),
    )
    assert old_get.status_code == 404


def test_remove_image_from_all_questions(client: TestClient, admin_token: str) -> None:
    quiz_id, pairs = _create_quiz_with_questions(client, admin_token)
    media = _upload(
        client,
        admin_token,
        data=JPEG_BYTES,
        filename="shared.jpg",
        category="question_image",
        content_type="image/jpeg",
        quiz_id=quiz_id,
    ).json()["data"]

    applied = client.post(
        f"/api/v1/media/{media['id']}/apply-to-all",
        headers=_auth(admin_token),
        json={"quizId": quiz_id},
    )
    assert applied.status_code == 200, applied.text

    removed = client.post(
        f"/api/v1/media/{media['id']}/remove-from-all",
        headers=_auth(admin_token),
        json={"quizId": quiz_id},
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["data"]["clearedCount"] == 4

    for section_id, question_id in pairs:
        question = client.get(
            f"/api/v1/quizzes/{quiz_id}/sections/{section_id}/questions/{question_id}",
            headers=_auth(admin_token),
        )
        assert question.json()["data"].get("mediaFileId") in (None, "")

    still = client.get(
        f"/api/v1/media/{media['id']}",
        headers=_auth(admin_token),
    )
    assert still.status_code == 200


def test_override_one_question_after_apply_to_all(
    client: TestClient, admin_token: str
) -> None:
    quiz_id, pairs = _create_quiz_with_questions(
        client, admin_token, section_count=1, questions_per_section=3
    )
    section_id = pairs[0][0]

    shared = _upload(
        client,
        admin_token,
        data=JPEG_BYTES,
        filename="shared.jpg",
        category="question_image",
        content_type="image/jpeg",
        quiz_id=quiz_id,
    ).json()["data"]
    override = _upload(
        client,
        admin_token,
        data=PNG_BYTES,
        filename="special.png",
        category="question_image",
        content_type="image/png",
        quiz_id=quiz_id,
    ).json()["data"]

    applied = client.post(
        f"/api/v1/media/{shared['id']}/apply-to-all",
        headers=_auth(admin_token),
        json={"quizId": quiz_id},
    )
    assert applied.status_code == 200

    target_id = pairs[1][1]
    client.post(
        f"/api/v1/media/{override['id']}/attach",
        headers=_auth(admin_token),
        json={
            "quizId": quiz_id,
            "sectionId": section_id,
            "questionId": target_id,
        },
    )

    for _, question_id in pairs:
        data = client.get(
            f"/api/v1/quizzes/{quiz_id}/sections/{section_id}/questions/{question_id}",
            headers=_auth(admin_token),
        ).json()["data"]
        if question_id == target_id:
            assert data["mediaFileId"] == override["id"]
        else:
            assert data["mediaFileId"] == shared["id"]

    listed = client.get(
        f"/api/v1/media?quizId={quiz_id}",
        headers=_auth(admin_token),
    ).json()["data"]["items"]
    assert {item["id"] for item in listed} == {shared["id"], override["id"]}


def test_apply_to_all_skips_incompatible_audio_questions(
    client: TestClient, admin_token: str
) -> None:
    quiz = client.post(
        "/api/v1/quizzes",
        headers=_auth(admin_token),
        json={"title": "Mixed types"},
    ).json()["data"]
    quiz_id = quiz["id"]
    section_id = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections",
        headers=_auth(admin_token),
        json={"name": "Round"},
    ).json()["data"]["id"]

    text_q = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections/{section_id}/questions",
        headers=_auth(admin_token),
        json={"questionType": "Text", "promptText": "Text?"},
    ).json()["data"]["id"]
    audio_q = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections/{section_id}/questions",
        headers=_auth(admin_token),
        json={"questionType": "Audio", "promptText": "Audio?"},
    ).json()["data"]["id"]

    media = _upload(
        client,
        admin_token,
        data=JPEG_BYTES,
        filename="pic.jpg",
        category="question_image",
        content_type="image/jpeg",
        quiz_id=quiz_id,
    ).json()["data"]

    response = client.post(
        f"/api/v1/media/{media['id']}/apply-to-all",
        headers=_auth(admin_token),
        json={"quizId": quiz_id},
    )
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["updatedCount"] == 1
    assert body["skippedCount"] == 1
    assert body["questionIds"] == [text_q]

    audio = client.get(
        f"/api/v1/quizzes/{quiz_id}/sections/{section_id}/questions/{audio_q}",
        headers=_auth(admin_token),
    ).json()["data"]
    assert audio.get("mediaFileId") in (None, "")
