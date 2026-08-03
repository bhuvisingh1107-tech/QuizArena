"""Verify Excel export sheet structure matches the production contract."""

from __future__ import annotations

from io import BytesIO
from uuid import UUID

from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.services.response_service import ResponseService
from app.services.results_service import ResultsService
from tests.integration.test_scoring import _close_and_reveal, _setup_open_question


def test_export_xlsx_sheets_and_columns(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room, option_ids, [joined] = _setup_open_question(
        client,
        admin_token,
        db_session,
        title="Export XLSX",
        joiners=[("Ann", "ann@example.com")],
    )
    room_id = UUID(room["id"])
    ResponseService(db_session).submit(
        room_id=room_id,
        participant_id=UUID(joined["participant"]["id"]),
        option_ids=[UUID(option_ids[0])],
        require_connected=False,
    )
    _close_and_reveal(db_session, room_id)

    raw = ResultsService(db_session).export_xlsx(room_id)
    wb = load_workbook(BytesIO(raw))
    assert wb.sheetnames == ["Participants", "Every answer", "Timeline"]

    participants = list(wb["Participants"].iter_rows(values_only=True))
    assert participants[0] == (
        "Participant",
        "Rank",
        "Score",
        "Correct",
        "Incorrect",
        "Accuracy",
        "Average Response Time",
        "Fastest Response",
        "Longest Streak",
    )
    assert participants[1][0] == "Ann"
    assert participants[1][1] == 1
    assert participants[1][2] == 10
    assert participants[1][3] == 1

    answers = list(wb["Every answer"].iter_rows(values_only=True))
    assert answers[0] == (
        "Participant",
        "Question Number",
        "Question ID",
        "Question Text",
        "Selected Option",
        "Correct Option",
        "Correct/Incorrect",
        "Points Awarded",
        "Time Taken",
        "Timestamp",
        "Time Bonus",
        "Streak Bonus",
    )
    assert answers[1][0] == "Ann"
    assert answers[1][6] == "Correct"

    timeline = list(wb["Timeline"].iter_rows(values_only=True))
    assert timeline[0] == ("Event", "Timestamp", "Details")
    events = {row[0] for row in timeline[1:]}
    assert "Answer Submitted" in events or "Question Shown" in events or "Room Created" in events


def test_submit_emits_leaderboard_updated(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room, option_ids, [joined] = _setup_open_question(
        client,
        admin_token,
        db_session,
        title="Live LB Submit",
        joiners=[("Ann", "ann@example.com")],
    )
    result = ResponseService(db_session).submit(
        room_id=UUID(room["id"]),
        participant_id=UUID(joined["participant"]["id"]),
        option_ids=[UUID(option_ids[0])],
        require_connected=False,
    )
    types = [e.type for e in result.events]
    assert "leaderboard:updated" in types
    board = next(e for e in result.events if e.type == "leaderboard:updated")
    assert board.audience == "room"
    assert board.payload["entries"][0]["displayName"] == "Ann"
    assert board.payload["entries"][0]["score"] == 10
