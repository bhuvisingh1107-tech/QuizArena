"""Live presentation analytics payloads (option distribution, section/session highlights)."""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.enums import ParticipantState
from app.models.session_question import SessionQuestion
from app.repositories.participant_repository import ParticipantRepository
from app.repositories.response_repository import ResponseRepository
from app.services.leaderboard_service import LeaderboardService
from app.services.results_service import assign_competition_ranks


class DisplayStatsService:
    """Compute projector-facing stats without duplicating scoring logic."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._participants = ParticipantRepository(session)
        self._responses = ResponseRepository(session)

    def option_distribution(self, question: SessionQuestion) -> list[dict]:
        responses = self._responses.list_for_question(question.id)
        selection_counts: dict[UUID, int] = defaultdict(int)
        answered = 0
        for response in responses:
            if response.is_unanswered or response.submitted_at is None:
                continue
            answered += 1
            for raw_id in response.selected_option_ids or []:
                try:
                    selection_counts[UUID(str(raw_id))] += 1
                except (TypeError, ValueError):
                    continue

        options = sorted(question.options, key=lambda o: o.sort_order)
        out: list[dict] = []
        for opt in options:
            count = int(selection_counts.get(opt.id, 0))
            percent = round((count / answered) * 100.0, 1) if answered else 0.0
            out.append(
                {
                    "optionId": str(opt.id),
                    "text": opt.text,
                    "selectedCount": count,
                    "percent": percent,
                    "isCorrect": bool(opt.is_correct),
                }
            )
        return out

    def reveal_payload_extras(self, question: SessionQuestion) -> dict:
        distribution = self.option_distribution(question)
        responses = self._responses.list_for_question(question.id)
        answered = sum(
            1
            for r in responses
            if r.submitted_at is not None and not r.is_unanswered
        )
        correct = sum(1 for r in responses if r.is_correct)
        explanation = None
        if question.source_question_id is not None:
            from app.models.question import Question

            source = self._session.get(Question, question.source_question_id)
            if source is not None:
                explanation = source.explanation
        accuracy = round((correct / answered) * 100.0, 1) if answered else 0.0
        return {
            "optionDistribution": distribution,
            "explanation": explanation,
            "answeredCount": answered,
            "correctCount": correct,
            "accuracyPercent": accuracy,
        }

    def section_break_extras(self, room_id: UUID, section_id: UUID) -> dict:
        board = LeaderboardService(self._session).snapshot(room_id)
        participants = [
            p
            for p in self._participants.list_for_room(room_id)
            if p.state
            not in {
                ParticipantState.BANNED,
                ParticipantState.KICKED,
                ParticipantState.SESSION_ENDED,
            }
        ]
        from app.repositories.live_room_repository import LiveRoomRepository

        room = LiveRoomRepository(self._session).get_by_id(room_id)
        section_questions = [
            q
            for q in (room.session_questions if room else [])
            if q.session_section_id == section_id
        ]
        question_ids = {q.id for q in section_questions}
        accuracies: list[float] = []
        for q in section_questions:
            responses = self._responses.list_for_question(q.id)
            answered = [
                r
                for r in responses
                if r.submitted_at is not None and not r.is_unanswered
            ]
            if not answered:
                continue
            correct = sum(1 for r in answered if r.is_correct)
            accuracies.append((correct / len(answered)) * 100.0)

        avg_accuracy = round(sum(accuracies) / len(accuracies), 1) if accuracies else 0.0
        return {
            "leaderboard": board.get("entries"),
            "podium": board.get("podium"),
            "sectionStats": {
                "questionCount": len(section_questions),
                "participantCount": len(participants),
                "averageAccuracy": avg_accuracy,
            },
            "top3": (board.get("podium") or {}).get("entries") or board.get("entries", [])[:3],
        }

    def session_highlights(self, room_id: UUID) -> dict:
        board = LeaderboardService(self._session).snapshot(room_id)
        participants = [
            p
            for p in self._participants.list_for_room(room_id)
            if p.state
            not in {
                ParticipantState.BANNED,
                ParticipantState.KICKED,
                ParticipantState.SESSION_ENDED,
            }
        ]
        scores = [int(p.total_score or 0) for p in participants]
        average_score = round(sum(scores) / len(scores), 1) if scores else 0.0

        from app.repositories.live_room_repository import LiveRoomRepository

        room = LiveRoomRepository(self._session).get_by_id(room_id)
        questions = list(room.session_questions) if room else []

        hardest: dict | None = None
        most_missed: dict | None = None
        fastest: dict | None = None
        best_accuracy = 101.0
        worst_miss_rate = -1.0
        best_time_ms: int | None = None

        for index, question in enumerate(sorted(questions, key=lambda q: q.sort_order)):
            responses = self._responses.list_for_question(question.id)
            answered = [
                r
                for r in responses
                if r.submitted_at is not None and not r.is_unanswered
            ]
            if answered:
                correct = sum(1 for r in answered if r.is_correct)
                accuracy = (correct / len(answered)) * 100.0
                miss_rate = 100.0 - accuracy
                summary = {
                    "questionId": str(question.id),
                    "questionIndex": index,
                    "promptText": question.prompt_text,
                    "accuracyPercent": round(accuracy, 1),
                    "missPercent": round(miss_rate, 1),
                }
                if accuracy < best_accuracy:
                    best_accuracy = accuracy
                    hardest = summary
                if miss_rate > worst_miss_rate:
                    worst_miss_rate = miss_rate
                    most_missed = summary

            for response in answered:
                if response.response_time_ms is None:
                    continue
                if best_time_ms is None or response.response_time_ms < best_time_ms:
                    best_time_ms = int(response.response_time_ms)
                    owner = next(
                        (p for p in participants if p.id == response.participant_id),
                        None,
                    )
                    fastest = {
                        "participantId": str(response.participant_id),
                        "displayName": owner.display_name if owner else "Player",
                        "responseTimeMs": best_time_ms,
                        "questionId": str(question.id),
                        "promptText": question.prompt_text,
                    }

        ranked = assign_competition_ranks(participants)
        winner = None
        if ranked:
            top = ranked[0]
            winner = {
                "participantId": str(top.participant.id),
                "displayName": top.participant.display_name,
                "score": int(top.participant.total_score or 0),
                "rank": top.rank,
            }

        return {
            "averageScore": average_score,
            "participantCount": len(participants),
            "winner": winner,
            "hardestQuestion": hardest,
            "mostMissedQuestion": most_missed,
            "fastestAnswer": fastest,
            "leaderboard": board.get("entries"),
            "podium": board.get("podium"),
        }
