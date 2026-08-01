"""Server-driven automatic question progression (timer → reveal → next).

Schedules asyncio tasks per live room. Cancels on pause/end; reschedules on resume.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)

# Dwell after reveal / section break before advancing (seconds).
REVEAL_DWELL_SECONDS = 5.0
# Used when a question has no timeLimitSeconds during live auto-play.
DEFAULT_QUESTION_SECONDS = 30


class AutoProgressionScheduler:
    """One background pipeline at a time per room."""

    def __init__(self) -> None:
        self._tasks: dict[UUID, asyncio.Task[None]] = {}
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        logger.info("Auto-progression scheduler ready")

    async def stop(self) -> None:
        async with self._lock:
            tasks = list(self._tasks.values())
            self._tasks.clear()
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass

    def cancel_room(self, room_id: UUID) -> None:
        task = self._tasks.pop(room_id, None)
        if task is not None and not task.done():
            task.cancel()

    def schedule_question(
        self,
        room_id: UUID,
        *,
        ends_at_epoch: float | None,
        question_id: UUID | None = None,
    ) -> None:
        """After question:started — wait until ends_at (or default), then close→reveal→next."""
        self.cancel_room(room_id)
        if ends_at_epoch is None:
            ends_at_epoch = time.time() + DEFAULT_QUESTION_SECONDS
        task = asyncio.create_task(
            self._run_question_cycle(room_id, ends_at_epoch, question_id),
            name=f"auto-progress-{room_id}",
        )
        self._tasks[room_id] = task
        task.add_done_callback(lambda done, rid=room_id: self._cleanup(rid, done))

    def notify_all_answered(self, room_id: UUID) -> None:
        """Early-close when every eligible participant has submitted."""
        self.cancel_room(room_id)
        task = asyncio.create_task(
            self._run_from_close(room_id),
            name=f"auto-progress-all-answered-{room_id}",
        )
        self._tasks[room_id] = task
        task.add_done_callback(lambda done, rid=room_id: self._cleanup(rid, done))

    def resume_from_question_state(self, room_id: UUID) -> None:
        """Continue auto-progression after pause during close/reveal/advance."""
        self.cancel_room(room_id)
        task = asyncio.create_task(
            self._resume_pipeline(room_id),
            name=f"auto-progress-resume-{room_id}",
        )
        self._tasks[room_id] = task
        task.add_done_callback(lambda done, rid=room_id: self._cleanup(rid, done))

    async def _resume_pipeline(self, room_id: UUID) -> None:
        from app.models.enums import SessionQuestionState

        try:
            state = await asyncio.to_thread(self._question_state, room_id)
            if state is None:
                return
            if state == SessionQuestionState.OPEN:
                return
            if state == SessionQuestionState.CLOSED:
                await self._reveal_and_broadcast(room_id)
                await asyncio.sleep(REVEAL_DWELL_SECONDS)
                await self._advance_and_broadcast(room_id)
                return
            if state in {SessionQuestionState.REVEALED, SessionQuestionState.SCORED}:
                await asyncio.sleep(REVEAL_DWELL_SECONDS)
                await self._advance_and_broadcast(room_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Auto-progression resume failed for room %s", room_id)

    def _question_state(self, room_id: UUID):
        from app.api.deps import get_session_factory
        from app.models.enums import RoomState
        from app.services.quiz_execution_service import QuizExecutionService

        session = get_session_factory()()
        try:
            state = QuizExecutionService(session).get_execution_state(room_id)
            if state.room.state != RoomState.ACTIVE:
                return None
            if state.question is None:
                return None
            return state.question.state
        finally:
            session.close()

    def _cleanup(self, room_id: UUID, done: asyncio.Task[None]) -> None:
        current = self._tasks.get(room_id)
        if current is done:
            self._tasks.pop(room_id, None)

    async def _run_question_cycle(
        self,
        room_id: UUID,
        ends_at_epoch: float,
        question_id: UUID | None,
    ) -> None:
        delay = max(0.0, ends_at_epoch - time.time())
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            raise
        if not await asyncio.to_thread(self._still_open, room_id, question_id):
            return
        await self._run_from_close(room_id)

    async def _run_from_close(self, room_id: UUID) -> None:
        try:
            await self._close_and_broadcast(room_id)
            await asyncio.sleep(0.05)
            await self._reveal_and_broadcast(room_id)
            await asyncio.sleep(REVEAL_DWELL_SECONDS)
            await self._advance_and_broadcast(room_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Auto-progression failed for room %s", room_id)

    def _still_open(self, room_id: UUID, question_id: UUID | None) -> bool:
        from app.api.deps import get_session_factory
        from app.models.enums import RoomState, SessionQuestionState
        from app.services.quiz_execution_service import QuizExecutionService

        session = get_session_factory()()
        try:
            state = QuizExecutionService(session).get_execution_state(room_id)
            if state.room.state != RoomState.ACTIVE:
                return False
            if state.question is None or state.question.state != SessionQuestionState.OPEN:
                return False
            if question_id is not None and state.question.id != question_id:
                return False
            return True
        finally:
            session.close()

    async def _close_and_broadcast(self, room_id: UUID) -> None:
        result = await asyncio.to_thread(self._sync_close, room_id)
        if result is not None:
            await self._broadcast_result(room_id, result)

    async def _reveal_and_broadcast(self, room_id: UUID) -> None:
        result = await asyncio.to_thread(self._sync_reveal, room_id)
        if result is not None:
            await self._broadcast_result(room_id, result)

    async def _advance_and_broadcast(self, room_id: UUID) -> None:
        result = await asyncio.to_thread(self._sync_advance, room_id)
        if result is None:
            return
        await self._broadcast_result(room_id, result)

        if any(e.type == "section:break" for e in result.events):
            await asyncio.sleep(REVEAL_DWELL_SECONDS)
            continued = await asyncio.to_thread(self._sync_continue_section, room_id)
            if continued is not None:
                await self._broadcast_result(room_id, continued)
                self._schedule_from_events(room_id, continued.events)
            return

        self._schedule_from_events(room_id, result.events)

    def _schedule_from_events(self, room_id: UUID, events: list[Any]) -> None:
        from app.api.websocket.broadcast_helpers import schedule_after_question_started

        schedule_after_question_started(room_id, events)

    def _sync_close(self, room_id: UUID) -> Any | None:
        from app.api.deps import get_session_factory
        from app.core.exceptions import QuizArenaError
        from app.models.enums import RoomState, SessionQuestionState
        from app.services.quiz_execution_service import QuizExecutionService

        session = get_session_factory()()
        try:
            execution = QuizExecutionService(session)
            state = execution.get_execution_state(room_id)
            if state.room.state != RoomState.ACTIVE:
                return None
            if state.question is None or state.question.state != SessionQuestionState.OPEN:
                return None
            return execution.close_question(room_id)
        except QuizArenaError as exc:
            logger.info("Auto-close skipped for %s: %s", room_id, exc.code)
            return None
        finally:
            session.close()

    def _sync_reveal(self, room_id: UUID) -> Any | None:
        from app.api.deps import get_session_factory
        from app.core.exceptions import QuizArenaError
        from app.models.enums import RoomState, SessionQuestionState
        from app.services.quiz_execution_service import QuizExecutionService

        session = get_session_factory()()
        try:
            execution = QuizExecutionService(session)
            state = execution.get_execution_state(room_id)
            if state.room.state != RoomState.ACTIVE:
                return None
            if state.question is None:
                return None
            if state.question.state not in {
                SessionQuestionState.CLOSED,
                SessionQuestionState.REVEALED,
                SessionQuestionState.SCORED,
            }:
                return None
            return execution.reveal_answer(room_id)
        except QuizArenaError as exc:
            logger.info("Auto-reveal skipped for %s: %s", room_id, exc.code)
            return None
        finally:
            session.close()

    def _sync_advance(self, room_id: UUID) -> Any | None:
        from app.api.deps import get_session_factory
        from app.core.exceptions import QuizArenaError
        from app.models.enums import RoomState
        from app.services.live_room_service import LiveRoomService
        from app.services.quiz_execution_service import QuizExecutionService

        session = get_session_factory()()
        try:
            from app.config import get_settings

            rooms = LiveRoomService(session, get_settings())
            execution = QuizExecutionService(session)
            room = rooms.get(room_id)
            if room.state == RoomState.SECTION_BREAK:
                return execution.next_section(room_id)
            if room.state != RoomState.ACTIVE:
                return None
            return execution.next_question(room_id)
        except QuizArenaError as exc:
            logger.info("Auto-advance skipped for %s: %s", room_id, exc.code)
            return None
        finally:
            session.close()

    def _sync_continue_section(self, room_id: UUID) -> Any | None:
        from app.api.deps import get_session_factory
        from app.core.exceptions import QuizArenaError
        from app.services.quiz_execution_service import QuizExecutionService

        session = get_session_factory()()
        try:
            return QuizExecutionService(session).next_section(room_id)
        except QuizArenaError as exc:
            logger.info("Auto section continue skipped for %s: %s", room_id, exc.code)
            return None
        finally:
            session.close()

    async def _broadcast_result(self, room_id: UUID, result: Any) -> None:
        from app.api.websocket.broadcast_helpers import broadcast_execution_events

        await broadcast_execution_events(room_id, result.events)


auto_progression = AutoProgressionScheduler()
