"""Verify Excel export sheet structure matches the production contract."""

from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from uuid import UUID

from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.models.response import Response
from app.services.response_service import ResponseService
from app.services.results_service import ResultsService, format_export_timestamp
from tests.integration.test_scoring import _close_and_reveal, _setup_open_question

EVERY_ANSWERS_HEADERS = (
    "Participant Name",
    "Participant ID",
    "Question Number",
    "Question ID",
    "Question Text",
    "Selected Option",
    "Correct Option",
    "Correct",
    "Question Shown Timestamp",
    "Answer Submitted Timestamp",
    "Response Time (milliseconds)",
    "Base Score",
    "Time Bonus",
    "Streak Bonus",
    "Total Score Awarded",
    "Rank Before Submission",
    "Rank After Submission",
)

TIMELINE_HEADERS = (
    "Timestamp",
    "Event",
    "Participant",
    "Question Number",
    "Selected Option",
)


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
    participant_id = UUID(joined["participant"]["id"])
    ResponseService(db_session).submit(
        room_id=room_id,
        participant_id=participant_id,
        option_ids=[UUID(option_ids[0])],
        require_connected=False,
    )
    _close_and_reveal(db_session, room_id)

    raw = ResultsService(db_session).export_xlsx(room_id)
    wb = load_workbook(BytesIO(raw))
    assert wb.sheetnames == ["Participants", "Every Answers", "Timeline"]

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

    answers = list(wb["Every Answers"].iter_rows(values_only=True))
    assert answers[0] == EVERY_ANSWERS_HEADERS
    row = answers[1]
    assert row[0] == "Ann"
    assert row[1] == str(participant_id)
    assert row[2] == 1
    assert row[3]  # Question ID
    assert row[5]  # Selected Option text
    assert row[6]  # Correct Option text
    assert row[7] is True
    assert isinstance(row[8], str) and "T" in row[8]  # Question Shown Timestamp
    assert isinstance(row[9], str) and "T" in row[9]  # Answer Submitted Timestamp
    assert row[9].endswith("Z") or "+" in row[9]
    # Millisecond precision: ...SSS Z or ...SSS+00:00 style → at least 3 fractional digits
    assert "." in row[9]
    assert row[10] is not None  # Response Time ms — stored, not derived in export
    assert row[11] == 10  # Base Score
    assert row[12] == 0  # Time Bonus
    assert row[13] == 0  # Streak Bonus
    assert row[14] == 10  # Total Score Awarded
    assert row[15] == 1  # Rank Before
    assert row[16] == 1  # Rank After

    # Export must use the persisted server submitted_at, not recompute from response time.
    db_response = db_session.query(Response).filter(Response.participant_id == participant_id).one()
    assert db_response.submitted_at is not None
    assert row[9] == format_export_timestamp(db_response.submitted_at)
    assert row[10] == db_response.response_time_ms
    assert db_response.rank_before == 1
    assert db_response.rank_after == 1

    timeline = list(wb["Timeline"].iter_rows(values_only=True))
    assert timeline[0] == TIMELINE_HEADERS
    answer_rows = [r for r in timeline[1:] if r[1] == "Answer Submitted"]
    assert answer_rows, "Timeline must include Answer Submitted events"
    submitted = answer_rows[0]
    assert isinstance(submitted[0], str) and "T" in submitted[0]
    assert submitted[2] == "Ann"
    assert submitted[3] == 1
    assert submitted[4]  # Selected Option


def test_format_export_timestamp_millisecond_precision() -> None:
    dt = datetime(2026, 8, 4, 12, 0, 0, 123456, tzinfo=UTC)
    assert format_export_timestamp(dt) == "2026-08-04T12:00:00.123Z"


def test_export_xlsx_ranks_change_across_participants(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    room, option_ids, joiners = _setup_open_question(
        client,
        admin_token,
        db_session,
        title="Export Ranks",
        joiners=[("Ann", "ann@example.com"), ("Bob", "bob@example.com")],
    )
    room_id = UUID(room["id"])
    # Ann correct, Bob incorrect
    ResponseService(db_session).submit(
        room_id=room_id,
        participant_id=UUID(joiners[0]["participant"]["id"]),
        option_ids=[UUID(option_ids[0])],
        require_connected=False,
    )
    ResponseService(db_session).submit(
        room_id=room_id,
        participant_id=UUID(joiners[1]["participant"]["id"]),
        option_ids=[UUID(option_ids[1])],
        require_connected=False,
    )
    _close_and_reveal(db_session, room_id)

    wb = load_workbook(BytesIO(ResultsService(db_session).export_xlsx(room_id)))
    answers = list(wb["Every Answers"].iter_rows(values_only=True))
    by_name = {row[0]: row for row in answers[1:]}
    assert by_name["Ann"][15] == 1  # before: both tied at 0 → competition rank 1
    assert by_name["Ann"][16] == 1  # after: Ann leads
    assert by_name["Bob"][15] == 1
    assert by_name["Bob"][16] == 2
    assert by_name["Ann"][7] is True
    assert by_name["Bob"][7] is False
