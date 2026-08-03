"""Integration tests for AI quiz generation (mock provider)."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _run_job_sync(job_id: str, *, storage_path: str | None = None) -> None:
    from app.api.deps import get_session_factory
    from app.config import Settings
    from app.services.ai.generation_service import AiGenerationService

    session = get_session_factory()()
    try:
        settings = Settings(
            ai_provider="mock",
            storage_path=storage_path or Settings().storage_path,
        )
        AiGenerationService(session, settings).run_job(UUID(job_id))
    finally:
        session.close()


def test_topic_generation_review_and_save(
    client: TestClient,
    admin_token: str,
    monkeypatch,
) -> None:
    monkeypatch.setenv("AI_PROVIDER", "mock")
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.api.routers.ai_generation.ai_job_worker.enqueue",
        lambda _job_id: None,
    )

    created = client.post(
        "/api/v1/ai/generate/topic",
        headers=_auth(admin_token),
        json={
            "topic": "Basic Geometry",
            "questionCount": 6,
            "difficulty": "mixed",
            "questionKinds": ["mcq", "true_false"],
            "language": "en",
        },
    )
    assert created.status_code == 201, created.text
    job_id = created.json()["data"]["id"]

    _run_job_sync(job_id)

    detail = client.get(f"/api/v1/ai/jobs/{job_id}", headers=_auth(admin_token))
    assert detail.status_code == 200, detail.text
    data = detail.json()["data"]
    assert data["status"] == "completed"
    assert len(data["sections"]) >= 3
    assert sum(len(s["questions"]) for s in data["sections"]) >= 6
    assert data["sources"]

    first_q = data["sections"][0]["questions"][0]
    patched = client.patch(
        f"/api/v1/ai/question/{first_q['id']}",
        headers=_auth(admin_token),
        json={"promptText": "Edited geometry question?", "explanation": "Because shapes."},
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["promptText"] == "Edited geometry question?"

    saved = client.post(
        "/api/v1/ai/save",
        headers=_auth(admin_token),
        json={"jobId": job_id},
    )
    assert saved.status_code == 200, saved.text
    quiz_id = saved.json()["data"]["quizId"]

    quiz = client.get(f"/api/v1/quizzes/{quiz_id}", headers=_auth(admin_token))
    assert quiz.status_code == 200
    assert quiz.json()["data"]["status"] == "Draft"


def test_document_txt_upload_generation(
    client: TestClient,
    admin_token: str,
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("AI_PROVIDER", "mock")
    storage = tmp_path / "storage"
    storage.mkdir()
    monkeypatch.setenv("STORAGE_PATH", str(storage))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.api.routers.ai_generation.ai_job_worker.enqueue",
        lambda _job_id: None,
    )

    job = client.post(
        "/api/v1/ai/generate/document",
        headers=_auth(admin_token),
        json={"title": "DS Quiz", "questionCount": 3, "questionKinds": ["mcq"]},
    )
    assert job.status_code == 201, job.text
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
    assert upload.status_code == 200, upload.text

    _run_job_sync(job_id, storage_path=str(storage))

    detail = client.get(f"/api/v1/ai/jobs/{job_id}", headers=_auth(admin_token))
    assert detail.status_code == 200
    data = detail.json()["data"]
    assert data["status"] == "completed"
    assert data["sourceFiles"]
    assert len(data["sections"]) >= 1
