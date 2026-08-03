"""In-process async worker for AI generation jobs (v1).

Heavy Whisper/OCR should eventually move to a dedicated worker service.
This scheduler mirrors ``auto_progression`` and is safe for single-instance Render.
"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

logger = logging.getLogger(__name__)


class AiJobWorker:
    def __init__(self) -> None:
        self._tasks: dict[UUID, asyncio.Task[None]] = {}
        self._started = False

    async def start(self) -> None:
        self._started = True
        logger.info("AI generation worker ready")

    async def stop(self) -> None:
        self._started = False
        tasks = list(self._tasks.values())
        self._tasks.clear()
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass

    def enqueue(self, job_id: UUID) -> None:
        if job_id in self._tasks and not self._tasks[job_id].done():
            return
        task = asyncio.create_task(self._run(job_id), name=f"ai-job-{job_id}")
        self._tasks[job_id] = task
        task.add_done_callback(lambda done, rid=job_id: self._cleanup(rid, done))

    def cancel(self, job_id: UUID) -> None:
        task = self._tasks.pop(job_id, None)
        if task is not None and not task.done():
            task.cancel()

    def _cleanup(self, job_id: UUID, done: asyncio.Task[None]) -> None:
        current = self._tasks.get(job_id)
        if current is done:
            self._tasks.pop(job_id, None)

    async def _run(self, job_id: UUID) -> None:
        from app.api.deps import get_session_factory
        from app.services.ai.generation_service import AiGenerationService

        def _sync() -> None:
            session = get_session_factory()()
            try:
                AiGenerationService(session).run_job(job_id)
            finally:
                session.close()

        try:
            await asyncio.to_thread(_sync)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("AI generation job %s failed", job_id)


ai_job_worker = AiJobWorker()
