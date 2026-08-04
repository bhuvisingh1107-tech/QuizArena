"""Integration tests for AI quiz generation (mock provider)."""

from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _wait_job(client: TestClient, token: str, job_id: str, *, timeout: float = 15.0) -> dict:
    deadline = time.time() + timeout
    last: dict | None = None
    while time.time() < deadline:
        detail = client.get(f"/api/v1/ai/jobs/{job_id}", headers=_auth(token))
        assert detail.status_code == 200, detail.text
        last = detail.json()["data"]
        if last["status"] in {"completed", "failed", "cancelled"}:
            return last
        time.sleep(0.1)
    assert last is not None
    raise AssertionError(f"Job {job_id} did not finish; last status={last['status']}")


def test_topic_generation_auto_saves_to_my_quizzes(
    client: TestClient,
    admin_token: str,
    monkeypatch,
) -> None:
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("AI_API_KEY", "")
    from app.config import get_settings

    get_settings.cache_clear()

    created = client.post(
        "/api/v1/ai/generate/topic",
        headers=_auth(admin_token),
        json={
            "topic": "vector calculus",
            "questionCount": 12,
            "difficulty": "mixed",
            "questionKinds": ["mcq", "true_false", "multiple_correct", "fill_blank"],
            "language": "en",
        },
    )
    assert created.status_code == 202, created.text
    body = created.json()["data"]
    job_id = body["id"]
    assert body["status"] == "queued"

    data = _wait_job(client, admin_token, job_id)
    assert data["status"] == "completed", data
    assert data["progressPercent"] == 100
    assert len(data["sections"]) >= 3
    assert sum(len(s["questions"]) for s in data["sections"]) >= 6
    assert data["resultQuizId"], "auto-save should create a quiz"
    assert data["sources"]

    quiz = client.get(f"/api/v1/quizzes/{data['resultQuizId']}", headers=_auth(admin_token))
    assert quiz.status_code == 200
    assert quiz.json()["data"]["status"] == "Draft"

    listing = client.get("/api/v1/quizzes", headers=_auth(admin_token), params={"limit": 50})
    assert listing.status_code == 200
    ids = {item["id"] for item in listing.json()["data"]["items"]}
    assert data["resultQuizId"] in ids


def test_document_txt_upload_generation(
    client: TestClient,
    admin_token: str,
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("AI_API_KEY", "")
    storage = tmp_path / "storage"
    storage.mkdir()
    monkeypatch.setenv("STORAGE_PATH", str(storage))
    from app.config import get_settings

    get_settings.cache_clear()

    job = client.post(
        "/api/v1/ai/generate/document",
        headers=_auth(admin_token),
        json={"title": "DS Quiz", "questionCount": 3, "questionKinds": ["mcq"]},
    )
    assert job.status_code == 202, job.text
    job_id = job.json()["data"]["id"]

    sample = (
        "Chapter 1: Introduction\n\nData structures store data.\n\n"
        "Chapter 2: Arrays\n\nArrays are contiguous.\n\n"
        "Chapter 3: Linked Lists\n\nNodes point to next nodes.\n"
    ).encode("utf-8")

    upload = client.post(
        "/api/v1/ai/upload",
        headers=_auth(admin_token),
        data={"jobId": job_id},
        files={"file": ("notes.txt", sample, "text/plain")},
    )
    assert upload.status_code == 202, upload.text

    data = _wait_job(client, admin_token, job_id)
    assert data["status"] == "completed", data
    assert data["sourceFiles"]
    assert len(data["sections"]) >= 1
    assert data["resultQuizId"]


def test_legacy_ppt_rejected_with_clear_error(
    client: TestClient,
    admin_token: str,
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("AI_API_KEY", "")
    storage = tmp_path / "storage"
    storage.mkdir()
    monkeypatch.setenv("STORAGE_PATH", str(storage))
    from app.config import get_settings

    get_settings.cache_clear()

    job = client.post(
        "/api/v1/ai/generate/document",
        headers=_auth(admin_token),
        json={"title": "Legacy", "questionCount": 3},
    )
    job_id = job.json()["data"]["id"]
    upload = client.post(
        "/api/v1/ai/upload",
        headers=_auth(admin_token),
        data={"jobId": job_id},
        files={"file": ("old.ppt", b"not-a-real-ppt", "application/vnd.ms-powerpoint")},
    )
    assert upload.status_code == 422
    err = upload.json()["error"]
    assert err["code"] == "UNSUPPORTED_FILE_TYPE"
    assert "pptx" in err["message"].lower()
    assert "pip install" not in err["message"].lower()
