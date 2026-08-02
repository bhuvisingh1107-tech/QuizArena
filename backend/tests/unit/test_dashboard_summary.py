"""Unit tests for host dashboard summary aggregates."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.models import Base
from app.models.admin import Admin
from app.models.enums import AnswerRevealBehavior, QuestionAdvanceMode, QuizStatus, RoomState
from app.models.live_room import LiveRoom
from app.models.quiz import Quiz
from app.models.quiz_config import QuizConfig
from app.models.room_config import RoomConfig
from app.services.dashboard_service import DashboardService


@pytest.fixture()
def session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _host(session: Session, *, username: str = "host") -> Admin:
    admin = Admin(
        username=username,
        password_hash=hash_password("StrongPassw0rd!"),
        name="Host",
        email=f"{username}@example.com",
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)
    return admin


def test_summary_empty_host_returns_zeros(session: Session) -> None:
    host = _host(session)
    data = DashboardService(session).summary(owner_id=host.id)
    assert data.quizzes_total == 0
    assert data.quizzes_draft == 0
    assert data.quizzes_ready == 0
    assert data.quizzes_in_use == 0
    assert data.quizzes_archived == 0
    assert data.rooms_active == 0
    assert data.rooms_completed == 0
    assert data.participants_today == 0


def test_summary_with_quizzes(session: Session) -> None:
    host = _host(session)
    for status, title in (
        (QuizStatus.DRAFT, "Draft"),
        (QuizStatus.READY, "Ready"),
        (QuizStatus.ARCHIVED, "Archived"),
    ):
        quiz = Quiz(
            title=title,
            status=status,
            owner_id=host.id,
            config=QuizConfig(),
        )
        session.add(quiz)
    session.commit()

    data = DashboardService(session).summary(owner_id=host.id)
    assert data.quizzes_total == 3
    assert data.quizzes_draft == 1
    assert data.quizzes_ready == 1
    assert data.quizzes_archived == 1
    assert data.rooms_active == 0


def test_summary_with_live_rooms(session: Session) -> None:
    host = _host(session)
    quiz = Quiz(
        title="Live",
        status=QuizStatus.IN_USE,
        owner_id=host.id,
        config=QuizConfig(),
    )
    session.add(quiz)
    session.flush()
    room = LiveRoom(
        quiz_id=quiz.id,
        state=RoomState.LOBBY,
        room_code="ABC123",
        secret_token="secret-token-dashboard-test",
        quiz_title_snapshot=quiz.title,
        config=RoomConfig(
            question_advance_mode=QuestionAdvanceMode.MANUAL,
            answer_reveal_behavior=AnswerRevealBehavior.AFTER_EACH,
        ),
    )
    session.add(room)
    session.commit()

    data = DashboardService(session).summary(owner_id=host.id)
    assert data.quizzes_in_use == 1
    assert data.rooms_active == 1
    assert data.rooms_completed == 0
    assert data.participants_today == 0
