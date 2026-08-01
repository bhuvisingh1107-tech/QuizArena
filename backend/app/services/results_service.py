"""Read-only session results and analytics (admin)."""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select

from app.core.exceptions import NotFoundError
from app.models.participant import Participant
from app.models.response import Response
from app.models.session_question import SessionQuestion
from app.repositories.live_room_repository import LiveRoomRepository
from app.repositories.participant_repository import ParticipantRepository
from app.schemas.results import (
    LeaderboardEntryData,
    OptionDistributionData,
    PodiumData,
    QuestionAnalyticsData,
    ResultsData,
    ResultsRoomData,
    ResultsSummaryData,
    SectionAnalyticsData,
)


@dataclass(frozen=True)
class RankedParticipant:
    participant: Participant
    rank: int


def assign_competition_ranks(participants: list[Participant]) -> list[RankedParticipant]:
    """Sort by score DESC, joined_at ASC; assign competition ranks by score."""
    ordered = sorted(
        participants,
        key=lambda p: (-int(p.total_score or 0), p.joined_at),
    )
    ranked: list[RankedParticipant] = []
    i = 0
    while i < len(ordered):
        score = int(ordered[i].total_score or 0)
        j = i + 1
        while j < len(ordered) and int(ordered[j].total_score or 0) == score:
            j += 1
        competition_rank = i + 1
        for k in range(i, j):
            ranked.append(RankedParticipant(participant=ordered[k], rank=competition_rank))
        i = j
    return ranked


class ResultsService:
    """Compute room results, analytics, and CSV export from persisted data."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._rooms = LiveRoomRepository(session)
        self._participants = ParticipantRepository(session)

    def get_results(self, room_id: UUID) -> ResultsData:
        room = self._rooms.get_by_id(room_id)
        if room is None:
            raise NotFoundError("NOT_FOUND", "Live room not found")

        participants = self._participants.list_for_room(room_id)
        questions = sorted(room.session_questions, key=lambda q: q.sort_order)
        sections = sorted(room.session_sections, key=lambda s: s.sort_order)
        section_name_by_id = {s.id: s.name for s in sections}

        responses = self._list_responses_for_room(room_id)
        responses_by_question: dict[UUID, list[Response]] = defaultdict(list)
        responses_by_participant: dict[UUID, list[Response]] = defaultdict(list)
        for response in responses:
            responses_by_question[response.session_question_id].append(response)
            responses_by_participant[response.participant_id].append(response)

        ranked = assign_competition_ranks(participants)
        leaderboard = [self._leaderboard_entry(rp) for rp in ranked]
        podium = PodiumData(entries=leaderboard[:3])

        total_questions = len(questions)
        participant_count = len(participants)
        average_score = (
            sum(int(p.total_score or 0) for p in participants) / participant_count
            if participant_count
            else 0.0
        )
        average_accuracy = self._average_accuracy(participants, total_questions)
        average_response_time = self._average_response_time(responses)

        question_analytics = [
            self._question_analytics(
                question=question,
                question_index=index,
                section_name=section_name_by_id.get(question.session_section_id, ""),
                question_responses=responses_by_question.get(question.id, []),
                participant_count=participant_count,
            )
            for index, question in enumerate(questions)
        ]

        section_analytics = [
            self._section_analytics(
                section_id=section.id,
                name=section.name,
                section_questions=[q for q in questions if q.session_section_id == section.id],
                participants=participants,
                responses_by_participant=responses_by_participant,
            )
            for section in sections
        ]

        return ResultsData(
            room=ResultsRoomData(
                id=room.id,
                room_code=room.room_code,
                quiz_title_snapshot=room.quiz_title_snapshot,
                state=room.state,
                started_at=room.started_at,
                completed_at=room.completed_at,
            ),
            summary=ResultsSummaryData(
                participant_count=participant_count,
                average_score=round(average_score, 2),
                average_accuracy_percent=round(average_accuracy, 2),
                total_questions=total_questions,
                average_response_time_ms=average_response_time,
            ),
            leaderboard=leaderboard,
            podium=podium,
            question_analytics=question_analytics,
            section_analytics=section_analytics,
        )

    def list_participants_admin(self, room_id: UUID) -> tuple[list[Participant], list[int], int]:
        """Return participants with competition ranks for admin listing."""
        room = self._rooms.get_by_id(room_id)
        if room is None:
            raise NotFoundError("NOT_FOUND", "Live room not found")
        participants = self._participants.list_for_room(room_id)
        ranked = assign_competition_ranks(participants)
        return (
            [rp.participant for rp in ranked],
            [rp.rank for rp in ranked],
            len(ranked),
        )

    def export_csv(self, room_id: UUID) -> str:
        """Build CSV text for leaderboard export."""
        room = self._rooms.get_by_id(room_id)
        if room is None:
            raise NotFoundError("NOT_FOUND", "Live room not found")

        participants = self._participants.list_for_room(room_id)
        ranked = assign_competition_ranks(participants)

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "Rank",
                "Display Name",
                "Email",
                "Score",
                "Correct",
                "Incorrect",
                "Unanswered",
                "Streak",
            ]
        )
        for rp in ranked:
            p = rp.participant
            writer.writerow(
                [
                    rp.rank,
                    p.display_name,
                    p.email,
                    int(p.total_score or 0),
                    int(p.total_correct or 0),
                    int(p.total_incorrect or 0),
                    int(p.unanswered_count or 0),
                    int(p.streak or 0),
                ]
            )
        return buffer.getvalue()

    def _list_responses_for_room(self, room_id: UUID) -> list[Response]:
        stmt = (
            select(Response)
            .join(Participant, Response.participant_id == Participant.id)
            .where(Participant.live_room_id == room_id)
            .options(selectinload(Response.session_question))
        )
        return list(self._session.scalars(stmt).all())

    @staticmethod
    def _leaderboard_entry(rp: RankedParticipant) -> LeaderboardEntryData:
        p = rp.participant
        return LeaderboardEntryData(
            rank=rp.rank,
            participant_id=p.id,
            display_name=p.display_name,
            score=int(p.total_score or 0),
            streak=int(p.streak or 0),
            total_correct=int(p.total_correct or 0),
            total_incorrect=int(p.total_incorrect or 0),
            unanswered_count=int(p.unanswered_count or 0),
        )

    @staticmethod
    def _average_accuracy(participants: list[Participant], total_questions: int) -> float:
        if not participants or total_questions <= 0:
            return 0.0
        accuracies: list[float] = []
        for p in participants:
            correct = int(p.total_correct or 0)
            accuracies.append((correct / total_questions) * 100.0)
        return sum(accuracies) / len(accuracies)

    @staticmethod
    def _average_response_time(responses: list[Response]) -> float | None:
        times = [
            int(r.response_time_ms)
            for r in responses
            if r.response_time_ms is not None and not r.is_unanswered
        ]
        if not times:
            return None
        return round(sum(times) / len(times), 2)

    @staticmethod
    def _question_analytics(
        *,
        question: SessionQuestion,
        question_index: int,
        section_name: str,
        question_responses: list[Response],
        participant_count: int,
    ) -> QuestionAnalyticsData:
        correct = 0
        incorrect = 0
        answered = 0
        times: list[int] = []
        selection_counts: dict[UUID, int] = defaultdict(int)

        for response in question_responses:
            if response.is_unanswered or response.submitted_at is None:
                continue
            answered += 1
            if response.is_correct:
                correct += 1
            else:
                incorrect += 1
            if response.response_time_ms is not None:
                times.append(int(response.response_time_ms))
            for raw_id in response.selected_option_ids or []:
                try:
                    selection_counts[UUID(str(raw_id))] += 1
                except (TypeError, ValueError):
                    continue

        unanswered = max(0, participant_count - answered)

        answered_for_accuracy = correct + incorrect
        accuracy = (correct / answered_for_accuracy * 100.0) if answered_for_accuracy else 0.0
        avg_time = round(sum(times) / len(times), 2) if times else None

        options = sorted(question.options, key=lambda o: o.sort_order)
        distribution = [
            OptionDistributionData(
                option_id=opt.id,
                text=opt.text,
                selected_count=selection_counts.get(opt.id, 0),
                is_correct=bool(opt.is_correct),
            )
            for opt in options
        ]

        return QuestionAnalyticsData(
            question_id=question.id,
            question_index=question_index,
            prompt_text=question.prompt_text,
            section_name=section_name,
            submission_count=answered,
            correct_count=correct,
            incorrect_count=incorrect,
            unanswered_count=unanswered,
            accuracy_percent=round(accuracy, 2),
            average_response_time_ms=avg_time,
            option_distribution=distribution,
        )

    @staticmethod
    def _section_analytics(
        *,
        section_id: UUID,
        name: str,
        section_questions: list[SessionQuestion],
        participants: list[Participant],
        responses_by_participant: dict[UUID, list[Response]],
    ) -> SectionAnalyticsData:
        question_ids = {q.id for q in section_questions}
        question_count = len(section_questions)
        if not participants or not question_ids:
            return SectionAnalyticsData(
                section_id=section_id,
                name=name,
                average_score=0.0,
                question_count=question_count,
            )

        section_scores: list[float] = []
        for participant in participants:
            total = 0
            for response in responses_by_participant.get(participant.id, []):
                if response.session_question_id in question_ids:
                    total += int(response.total_points_earned or 0)
            section_scores.append(float(total))

        average = sum(section_scores) / len(section_scores)
        return SectionAnalyticsData(
            section_id=section_id,
            name=name,
            average_score=round(average, 2),
            question_count=question_count,
        )
