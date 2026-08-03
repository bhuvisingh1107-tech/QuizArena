"""Background AI generation runner.

Uses FastAPI ``BackgroundTasks`` (sync callable) so work runs after the HTTP
response without calling ``asyncio.create_task`` from a threadpool handler.
"""

from __future__ import annotations

import logging
import threading
from uuid import UUID

logger = logging.getLogger(__name__)


class AiJobWorker:
    """Tracks in-flight jobs for cancel + startup recovery."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cancelled: set[UUID] = set()
        self._running: set[UUID] = set()
        self._started = False

    async def start(self) -> None:
        self._started = True
        logger.info("AI generation worker ready (BackgroundTasks mode)")
        # Recover orphaned topic jobs left QUEUED after prior enqueue bugs.
        threading.Thread(target=self._recover_orphaned_jobs, name="ai-recover", daemon=True).start()

    async def stop(self) -> None:
        self._started = False
        with self._lock:
            self._cancelled.clear()
            self._running.clear()

    def is_cancelled(self, job_id: UUID) -> bool:
        with self._lock:
            return job_id in self._cancelled

    def enqueue(self, job_id: UUID) -> None:
        """Mark job runnable. Actual execution is scheduled via BackgroundTasks."""
        with self._lock:
            self._cancelled.discard(job_id)
        logger.info("AI job %s accepted for background execution", job_id)

    def schedule(self, background_tasks: object, job_id: UUID) -> None:
        """Register with FastAPI BackgroundTasks (preferred)."""
        self.enqueue(job_id)
        add_task = getattr(background_tasks, "add_task", None)
        if add_task is None:
            raise RuntimeError("BackgroundTasks unavailable")
        add_task(self.run_sync, job_id)

    def cancel(self, job_id: UUID) -> None:
        with self._lock:
            self._cancelled.add(job_id)
        logger.info("AI job %s cancel requested", job_id)

    def run_sync(self, job_id: UUID) -> None:
        """Execute generation in a worker thread (called by BackgroundTasks)."""
        with self._lock:
            if job_id in self._cancelled:
                logger.info("AI job %s skipped (cancelled before start)", job_id)
                return
            if job_id in self._running:
                logger.info("AI job %s already running — skip", job_id)
                return
            self._running.add(job_id)

        from app.api.deps import get_session_factory
        from app.services.ai.generation_service import AiGenerationService

        logger.info("AI job %s background run starting", job_id)
        session = get_session_factory()()
        try:
            if self.is_cancelled(job_id):
                logger.info("AI job %s cancelled before execution", job_id)
                return
            AiGenerationService(session).run_job(job_id)
            logger.info("AI job %s background run finished", job_id)
        except Exception:
            logger.exception("AI generation job %s failed", job_id)
        finally:
            session.close()
            with self._lock:
                self._running.discard(job_id)

    def _recover_orphaned_jobs(self) -> None:
        from sqlalchemy import select

        from app.api.deps import get_session_factory
        from app.models.ai_generation import AiGenerationJob
        from app.models.enums import AiGenerationMode, AiJobStatus

        try:
            session = get_session_factory()()
            try:
                rows = list(
                    session.scalars(
                        select(AiGenerationJob.id).where(
                            AiGenerationJob.mode == AiGenerationMode.TOPIC,
                            AiGenerationJob.status == AiJobStatus.QUEUED,
                        )
                    ).all()
                )
            finally:
                session.close()
        except Exception:
            logger.exception("Failed to scan for orphaned AI jobs")
            return

        if not rows:
            return
        logger.warning("Recovering %s orphaned QUEUED topic job(s)", len(rows))
        for job_id in rows:
            threading.Thread(
                target=self.run_sync,
                args=(job_id,),
                name=f"ai-recover-{job_id}",
                daemon=True,
            ).start()


ai_job_worker = AiJobWorker()
