"""Quality gate tests — placeholders must never be accepted."""

from __future__ import annotations

import pytest

from app.core.exceptions import ValidationError
from app.services.ai.quality import (
    assert_no_placeholders,
    find_placeholder_hits,
    validate_question_payload,
    validate_questions_batch,
)


def test_detects_classic_placeholders() -> None:
    assert find_placeholder_hits("concept #3")
    assert find_placeholder_hits("Plausible distractor A")
    assert find_placeholder_hits("Correct Foundations fact")
    assert find_placeholder_hits("This checks understanding of Arrays.")
    assert find_placeholder_hits("TODO: write explanation")
    assert find_placeholder_hits("Explanation goes here")
    assert find_placeholder_hits("TBD")
    assert find_placeholder_hits("<explanation>")
    assert find_placeholder_hits("{{explanation}}")
    assert find_placeholder_hits("Fill this later")


def test_rejects_stub_explanation() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_question_payload(
            {
                "promptText": "What is the capital of France?",
                "explanation": "Explanation goes here",
                "options": [
                    {"text": "Paris", "isCorrect": True},
                    {"text": "Lyon", "isCorrect": False},
                    {"text": "Marseille", "isCorrect": False},
                    {"text": "Nice", "isCorrect": False},
                ],
            },
            index=0,
        )
    assert exc.value.code == "AI_PLACEHOLDER_CONTENT"
    assert "question[0].explanation" in str(exc.value.message)


def test_rejects_placeholder_question() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_question_payload(
            {
                "promptText": "Which statement best describes concept #1?",
                "explanation": "This checks understanding of Foundations.",
                "options": [
                    {"text": "Correct Foundations fact", "isCorrect": True},
                    {"text": "Plausible distractor A", "isCorrect": False},
                    {"text": "Plausible distractor B", "isCorrect": False},
                    {"text": "Plausible distractor C", "isCorrect": False},
                ],
            },
            index=0,
        )
    assert exc.value.code == "AI_PLACEHOLDER_CONTENT"


def test_accepts_grounded_question() -> None:
    validate_question_payload(
        {
            "promptText": "Which scheduling algorithm minimizes average waiting time?",
            "explanation": (
                "Shortest Job First minimizes average waiting time among common "
                "non-preemptive scheduling algorithms covered in the material."
            ),
            "options": [
                {"text": "Shortest Job First (SJF)", "isCorrect": True},
                {"text": "First Come First Served", "isCorrect": False},
                {"text": "Round Robin", "isCorrect": False},
                {"text": "Priority Scheduling (starvation-prone)", "isCorrect": False},
            ],
        },
        index=0,
    )


def test_batch_rejects_empty() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_questions_batch([])
    assert exc.value.code == "AI_GENERATION_EMPTY"


def test_assert_no_placeholders_on_option() -> None:
    with pytest.raises(ValidationError):
        assert_no_placeholders("Distractor", field="option")
