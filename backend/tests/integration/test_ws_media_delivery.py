"""WebSocket question payloads must never carry image bytes — only media refs."""

from __future__ import annotations

import json
from io import BytesIO
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.websocket.events import ServerEventType
from app.models.enums import QuizStatus
from app.models.quiz import Quiz


JPEG_BYTES = b"\xff\xd8\xff" + b"\x00" * 64


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _recv_until(ws, event_type: str, *, limit: int = 30) -> dict:
    for _ in range(limit):
        msg = ws.receive_json()
        if msg.get("type") == event_type:
            return msg
    raise AssertionError(f"Did not receive event type {event_type}")


def _assert_no_binary_media(payload: dict) -> None:
    """Fail if any nested value looks like embedded image bytes/base64."""
    raw = json.dumps(payload)
    assert "base64" not in raw.lower()
    assert "data:image" not in raw.lower()
    assert "\\xff\\xd8\\xff" not in raw

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                assert key.lower() not in {
                    "imagebytes",
                    "imagedata",
                    "thumbnail",
                    "blob",
                    "binary",
                }
                if isinstance(value, (bytes, bytearray)):
                    raise AssertionError(f"Binary value found under key {key}")
                if isinstance(value, str) and len(value) > 500:
                    # Paths / prompts stay short; huge strings would be embedded media.
                    raise AssertionError(f"Unexpectedly large string under key {key}")
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)


def test_question_started_ws_sends_media_refs_only(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    quiz = client.post(
        "/api/v1/quizzes",
        headers=_auth(admin_token),
        json={"title": "WS Media Refs"},
    ).json()["data"]
    quiz_id = quiz["id"]
    section_id = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections",
        headers=_auth(admin_token),
        json={"name": "Round 1"},
    ).json()["data"]["id"]

    question = client.post(
        f"/api/v1/quizzes/{quiz_id}/sections/{section_id}/questions",
        headers=_auth(admin_token),
        json={"questionType": "Image", "promptText": "What is shown?"},
    ).json()["data"]
    question_id = question["id"]

    for text, correct, order in (("A", True, 0), ("B", False, 1)):
        opt = client.post(
            f"/api/v1/quizzes/{quiz_id}/sections/{section_id}/questions/{question_id}/options",
            headers=_auth(admin_token),
            json={"text": text, "isCorrect": correct, "sortOrder": order},
        )
        assert opt.status_code == 201, opt.text

    media = client.post(
        "/api/v1/media",
        headers=_auth(admin_token),
        data={"category": "question_image", "quizId": quiz_id},
        files={"file": ("prompt.jpg", BytesIO(JPEG_BYTES), "image/jpeg")},
    ).json()["data"]

    attach = client.post(
        f"/api/v1/media/{media['id']}/attach",
        headers=_auth(admin_token),
        json={
            "quizId": quiz_id,
            "sectionId": section_id,
            "questionId": question_id,
        },
    )
    assert attach.status_code == 200, attach.text

    row = db_session.get(Quiz, UUID(quiz_id))
    assert row is not None
    row.status = QuizStatus.READY
    db_session.commit()

    room = client.post(
        "/api/v1/live-rooms",
        headers=_auth(admin_token),
        json={"quizId": quiz_id},
    ).json()["data"]
    client.post(f"/api/v1/live-rooms/{room['id']}/open-lobby", headers=_auth(admin_token))
    started = client.post(
        f"/api/v1/live-rooms/{room['id']}/start",
        headers=_auth(admin_token),
    )
    assert started.status_code == 200, started.text

    with client.websocket_connect(
        f"/ws?role=admin&token={admin_token}&roomId={room['id']}",
    ) as ws:
        _recv_until(ws, ServerEventType.CONNECTION_ACK)
        _recv_until(ws, ServerEventType.RESYNC)
        ws.send_json({"type": "admin:start_question", "payload": {}})
        _recv_until(ws, ServerEventType.SECTION_STARTED)
        event = _recv_until(ws, ServerEventType.QUESTION_STARTED)

    question_payload = event["payload"]["question"]
    assert question_payload["mediaFileId"] == media["id"]
    assert question_payload["imageUrl"] == f"/api/v1/media/{media['id']}/content"
    _assert_no_binary_media(event["payload"])

    # Image bytes are served over HTTP only
    content = client.get(
        f"/api/v1/media/{media['id']}/content",
        headers=_auth(admin_token),
    )
    assert content.status_code == 200
    assert content.content == JPEG_BYTES
    assert "private" in content.headers.get("cache-control", "").lower()
