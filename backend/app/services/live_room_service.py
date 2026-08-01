"""Live room lifecycle and session snapshot (API_SPEC.md §11)."""

from __future__ import annotations

import secrets
import string
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.enums import LobbySubState, QuizStatus, RoomState, SessionQuestionState
from app.models.live_room import LiveRoom
from app.models.quiz import Quiz
from app.models.quiz_config import QuizConfig
from app.models.room_config import RoomConfig
from app.models.session_option import SessionOption
from app.models.session_question import SessionQuestion
from app.models.session_section import SessionSection
from app.repositories.live_room_repository import LiveRoomRepository
from app.schemas.live_room import LiveRoomCreateRequest, RoomConfigData
from app.services.state_machine import room_fsm

_ROOM_CODE_ALPHABET = string.ascii_uppercase + string.digits
_ROOM_CODE_LENGTH = 6
_MAX_CODE_ATTEMPTS = 32
_PUBLIC_APP_URL = "https://app.quizarena.com"


class LiveRoomService:
    """Create, configure, and control live rooms (no participant/WS execution)."""

    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings
        self._rooms = LiveRoomRepository(session)
        self._app_url = _PUBLIC_APP_URL
        if settings is not None and hasattr(settings, "public_app_url"):
            self._app_url = getattr(settings, "public_app_url") or _PUBLIC_APP_URL

    # ── URLs ──────────────────────────────────────────────────────────────

    def join_url(self, room_code: str) -> str:
        return f"{self._app_url.rstrip('/')}/join/{room_code}"

    def display_url(self, secret_token: str) -> str:
        return f"{self._app_url.rstrip('/')}/display/{secret_token}"

    def qr_target(self, room_code: str) -> str:
        return self.join_url(room_code)

    # ── CRUD / lifecycle ───────────────────────────────────────────────────

    def create(self, payload: LiveRoomCreateRequest) -> LiveRoom:
        if self._rooms.has_hosting_room():
            raise ConflictError(
                "ACTIVE_ROOM_EXISTS",
                "Only one live room may be hosted at a time (v1)",
            )

        quiz = self._rooms.get_quiz_for_snapshot(payload.quiz_id)
        if quiz is None:
            raise NotFoundError("QUIZ_NOT_FOUND", "Quiz not found")
        self._ensure_quiz_ready(quiz)

        room_code = self._generate_unique_room_code()
        secret_token = self._generate_unique_secret_token()
        config = self._build_room_config(quiz.config, payload.config)

        try:
            room = self._rooms.create_room(
                quiz_id=quiz.id,
                state=RoomState.SETUP,
                room_code=room_code,
                secret_token=secret_token,
                quiz_title_snapshot=quiz.title,
                config=config,
            )
            self._create_session_snapshot(room, quiz)
            quiz.status = QuizStatus.IN_USE
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            if "room_code" in str(exc).lower() or "uq" in str(exc).lower():
                raise ConflictError(
                    "DUPLICATE_JOIN_CODE",
                    "Generated join code collided; please retry",
                ) from exc
            raise

        from app.core.audit import audit

        created = self.get(room.id)
        audit(
            "room.create",
            room_id=str(created.id),
            room_code=created.room_code,
            quiz_id=str(created.quiz_id),
        )
        return created

    def list(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        state: RoomState | None = None,
    ) -> tuple[list[LiveRoom], int]:
        return self._rooms.list(offset=offset, limit=limit, state=state)

    def get(self, room_id: UUID) -> LiveRoom:
        room = self._rooms.get_by_id(room_id)
        if room is None:
            raise NotFoundError("LIVE_ROOM_NOT_FOUND", "Live room not found")
        return room

    def update_config(self, room_id: UUID, payload: RoomConfigData) -> LiveRoom:
        room = self.get(room_id)
        if room.state != RoomState.SETUP:
            raise ValidationError(
                "ROOM_CONFIG_IMMUTABLE",
                "Room configuration can only be updated while the room is in Setup",
            )
        if room.config is None:
            raise NotFoundError("ROOM_CONFIG_NOT_FOUND", "Room configuration not found")

        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise ValidationError("INVALID_ROOM_CONFIG", "No configuration fields provided")

        for field, value in updates.items():
            setattr(room.config, field, value)

        self._rooms.flush()
        self._session.commit()
        return self.get(room_id)

    def open_lobby(self, room_id: UUID) -> LiveRoom:
        room = self.get(room_id)
        room.state = room_fsm.transition(room.state, "open_lobby")
        room.lobby_sub_state = LobbySubState.OPEN
        self._rooms.flush()
        self._session.commit()
        return self.get(room_id)

    def toggle_lobby(self, room_id: UUID) -> LiveRoom:
        room = self.get(room_id)
        if room.state != RoomState.LOBBY:
            raise ValidationError(
                "INVALID_STATE_TRANSITION",
                f"Cannot toggle lobby when room state is '{room.state.value}'",
            )
        if room.lobby_sub_state == LobbySubState.OPEN:
            room.lobby_sub_state = LobbySubState.CLOSED
        else:
            room.lobby_sub_state = LobbySubState.OPEN
        self._rooms.flush()
        self._session.commit()
        return self.get(room_id)

    def start(self, room_id: UUID) -> LiveRoom:
        room = self.get(room_id)
        room.state = room_fsm.transition(room.state, "start")
        room.started_at = datetime.now(UTC)
        room.current_question_index = 0
        # Snapshot questions stay Pending until the host starts quiz execution.
        questions = sorted(room.session_questions, key=lambda q: q.sort_order)
        if questions:
            questions[0].state = SessionQuestionState.PENDING
        self._rooms.flush()
        self._session.commit()
        return self.get(room_id)

    def pause(self, room_id: UUID) -> LiveRoom:
        room = self.get(room_id)
        room.state = room_fsm.transition(room.state, "pause")
        if room.paused_at is None:
            room.paused_at = datetime.now(UTC)
        self._rooms.flush()
        self._session.commit()
        from app.core.audit import audit

        audit("room.pause", room_id=str(room_id))
        return self.get(room_id)

    def resume(self, room_id: UUID) -> LiveRoom:
        room = self.get(room_id)
        room.state = room_fsm.transition(room.state, "resume")
        if room.paused_at is not None:
            delta_ms = int((datetime.now(UTC) - room.paused_at).total_seconds() * 1000)
            room.pause_accumulated_ms = int(room.pause_accumulated_ms or 0) + max(0, delta_ms)
            room.paused_at = None
        self._rooms.flush()
        self._session.commit()
        from app.core.audit import audit

        audit("room.resume", room_id=str(room_id))
        return self.get(room_id)

    def end(self, room_id: UUID) -> LiveRoom:
        """End session → Completed (API_SPEC end / architecture endSession)."""
        room = self.get(room_id)
        room.state = room_fsm.transition(room.state, "end")
        room.completed_at = datetime.now(UTC)
        self._rooms.flush()
        self._session.commit()
        return self.get(room_id)

    def close(self, room_id: UUID) -> LiveRoom:
        room = self.get(room_id)
        room.state = room_fsm.transition(room.state, "close")
        room.codes_expired = True
        room.closed_at = datetime.now(UTC)
        room.lobby_sub_state = None
        quiz = self._rooms.get_quiz_for_snapshot(room.quiz_id)
        if quiz is not None and quiz.status == QuizStatus.IN_USE:
            quiz.status = QuizStatus.READY
        self._rooms.flush()
        self._session.commit()
        from app.core.audit import audit

        audit("room.close", room_id=str(room_id), state="Closed")
        return self.get(room_id)

    def delete(self, room_id: UUID) -> None:
        room = self.get(room_id)
        if room.state not in {RoomState.SETUP, RoomState.CLOSED}:
            raise ConflictError(
                "ROOM_NOT_DELETABLE",
                "Only rooms in Setup or Closed state can be deleted",
            )
        quiz_id = room.quiz_id
        was_setup = room.state == RoomState.SETUP
        self._rooms.delete(room)
        if was_setup:
            quiz = self._rooms.get_quiz_for_snapshot(quiz_id)
            if quiz is not None and quiz.status == QuizStatus.IN_USE:
                quiz.status = QuizStatus.READY
        self._session.commit()

    # ── Internals ──────────────────────────────────────────────────────────

    @staticmethod
    def _ensure_quiz_ready(quiz: Quiz) -> None:
        if quiz.status == QuizStatus.DELETED:
            raise NotFoundError("QUIZ_NOT_FOUND", "Quiz not found")
        if quiz.status == QuizStatus.ARCHIVED:
            raise ValidationError(
                "QUIZ_NOT_READY",
                "Archived quizzes cannot be used to create a live room",
            )
        if quiz.status == QuizStatus.DRAFT:
            raise ValidationError(
                "QUIZ_NOT_READY",
                "Quiz must be Ready before a live room can be created",
            )
        if quiz.status == QuizStatus.IN_USE:
            raise ConflictError(
                "QUIZ_IN_USE",
                "Quiz is already linked to an active live room",
            )
        if quiz.status != QuizStatus.READY:
            raise ValidationError(
                "QUIZ_NOT_READY",
                f"Quiz status '{quiz.status.value}' cannot be used for a live room",
            )

    def _build_room_config(
        self,
        quiz_config: QuizConfig | None,
        overrides: RoomConfigData | None,
    ) -> RoomConfig:
        if quiz_config is None:
            raise ValidationError("QUIZ_CONFIG_MISSING", "Quiz configuration is missing")

        data = {
            "question_advance_mode": quiz_config.question_advance_mode,
            "answer_reveal_behavior": quiz_config.answer_reveal_behavior,
            "time_bonus_enabled": quiz_config.time_bonus_enabled,
            "time_bonus_max_points": quiz_config.time_bonus_max_points,
            "streak_bonus_enabled": quiz_config.streak_bonus_enabled,
            "streak_bonus_rules": quiz_config.streak_bonus_rules,
            "question_order_shuffle": quiz_config.question_order_shuffle,
            "answer_option_shuffle": quiz_config.answer_option_shuffle,
        }
        if overrides is not None:
            data.update(overrides.model_dump(exclude_unset=True, exclude_none=True))

        return RoomConfig(**data)

    def _create_session_snapshot(self, room: LiveRoom, quiz: Quiz) -> None:
        """Deep-copy sections/questions/options into immutable session rows."""
        global_question_order = 0
        sections = sorted(quiz.sections, key=lambda s: s.sort_order)
        for section in sections:
            session_section = SessionSection(
                live_room_id=room.id,
                source_section_id=section.id,
                name=section.name,
                sort_order=section.sort_order,
            )
            self._rooms.add_session_section(session_section)

            questions = sorted(section.questions, key=lambda q: q.sort_order)
            for question in questions:
                session_question = SessionQuestion(
                    live_room_id=room.id,
                    session_section_id=session_section.id,
                    source_question_id=question.id,
                    question_type=question.question_type,
                    prompt_text=question.prompt_text,
                    media_file_id=question.media_file_id,
                    base_points=question.base_points,
                    time_limit_seconds=question.time_limit_seconds,
                    allow_multiple_correct=question.allow_multiple_correct,
                    sort_order=global_question_order,
                    state=SessionQuestionState.PENDING,
                )
                self._rooms.add_session_question(session_question)
                global_question_order += 1

                options = sorted(question.options, key=lambda o: o.sort_order)
                for option in options:
                    self._rooms.add_session_option(
                        SessionOption(
                            session_question_id=session_question.id,
                            source_option_id=option.id,
                            text=option.text,
                            is_correct=option.is_correct,
                            sort_order=option.sort_order,
                        ),
                    )

    def _generate_unique_room_code(self) -> str:
        for _ in range(_MAX_CODE_ATTEMPTS):
            code = "".join(
                secrets.choice(_ROOM_CODE_ALPHABET) for _ in range(_ROOM_CODE_LENGTH)
            )
            if not self._rooms.room_code_exists(code):
                return code
        raise ConflictError(
            "DUPLICATE_JOIN_CODE",
            "Unable to generate a unique join code; please retry",
        )

    def _generate_unique_secret_token(self) -> str:
        for _ in range(_MAX_CODE_ATTEMPTS):
            token = secrets.token_urlsafe(32)[:64]
            if not self._rooms.secret_token_exists(token):
                return token
        raise ConflictError(
            "DUPLICATE_SECRET_TOKEN",
            "Unable to generate a unique display token; please retry",
        )
