"""Unit tests for AI job worker BackgroundTasks scheduling."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.services.ai.job_worker import AiJobWorker


def test_schedule_uses_background_tasks(monkeypatch) -> None:
    worker = AiJobWorker()
    scheduled: list = []

    def fake_run(job_id):  # noqa: ANN001
        scheduled.append(job_id)

    monkeypatch.setattr(worker, "run_sync", fake_run)
    job_id = uuid4()
    tasks = SimpleNamespace(add_task=lambda fn, *args: fn(*args))
    worker.schedule(tasks, job_id)
    assert scheduled == [job_id]


def test_cancel_before_run_skips() -> None:
    worker = AiJobWorker()
    job_id = uuid4()
    worker.cancel(job_id)
    # Should return without opening a DB session / raising
    worker.run_sync(job_id)


def test_enqueue_alone_does_not_require_event_loop() -> None:
    worker = AiJobWorker()
    worker.enqueue(uuid4())
