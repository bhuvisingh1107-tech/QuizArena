"""Reject placeholder / template AI quiz content before it reaches users."""

from __future__ import annotations

import re
from typing import Any

from app.core.exceptions import ValidationError

# Patterns that indicate mock/template output — never save these.
_PLACEHOLDER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"concept\s*#\s*\d+", re.I),
    re.compile(r"\bdistractor\s*[a-d]\b", re.I),
    re.compile(r"^distractor\b", re.I),
    re.compile(r"plausible\s+distractor", re.I),
    re.compile(r"correct\s+(answer|option|fact)\b", re.I),
    re.compile(r"correct\s+\w+\s+fact", re.I),
    re.compile(r"^option\s*[a-d]\s*$", re.I),
    re.compile(r"^this checks understanding", re.I),
    re.compile(r"this checks understanding of", re.I),
    re.compile(r"\bplaceholder\b", re.I),
    re.compile(r"which statement best describes concept", re.I),
    re.compile(r"\bunrelated claim\b", re.I),
    re.compile(r"\bcontradictory claim\b", re.I),
    re.compile(r"lorem ipsum", re.I),
    re.compile(r"sample question", re.I),
    re.compile(r"fill in the blank: the key term for .+ #\d+", re.I),
    # Explicit stub / unfinished explanation markers
    re.compile(r"\btodo\b", re.I),
    re.compile(r"\btbd\b", re.I),
    re.compile(r"explanation goes here", re.I),
    re.compile(r"fill this later", re.I),
    re.compile(r"fill in later", re.I),
    re.compile(r"<\s*explanation\s*>", re.I),
    re.compile(r"\{\{\s*explanation\s*\}\}", re.I),
    re.compile(r"\{\{[^}]+\}\}"),
)

_GENERIC_SECTION_ONLY = re.compile(
    r"^(foundations|core ideas|applications|introduction|core concepts|practice|"
    r".+\s+foundations|.+\s+core ideas|.+\s+applications)$",
    re.I,
)


def find_placeholder_hits(text: str) -> list[str]:
    hits: list[str] = []
    for pattern in _PLACEHOLDER_PATTERNS:
        if pattern.search(text or ""):
            hits.append(pattern.pattern)
    return hits


def assert_no_placeholders(text: str, *, field: str) -> None:
    hits = find_placeholder_hits(text)
    if hits:
        raise ValidationError(
            "AI_PLACEHOLDER_CONTENT",
            f"Generated {field} contained template/placeholder text and was rejected. "
            "Please retry generation with a configured AI provider.",
            details=[{"field": field, "patterns": hits[:5]}],
        )


def validate_question_payload(item: dict[str, Any], *, index: int) -> None:
    """Raise if a single LLM question payload is invalid or templated."""
    from app.services.mcq_validation import (
        MCQ_ALL_FILLED,
        MCQ_DUPLICATES,
        MCQ_EXACTLY_FOUR,
        MCQ_ONE_CORRECT,
        MCQ_SELECT_CORRECT,
        OptionSnapshot,
        assert_mcq_options_valid,
        is_true_false_options,
    )

    prompt = str(item.get("promptText") or item.get("prompt_text") or "").strip()
    explanation = str(item.get("explanation") or "").strip()
    options = item.get("options") or []
    kind = str(item.get("kind") or "mcq").strip().lower()

    if len(prompt) < 12:
        raise ValidationError(
            "AI_QUESTION_INVALID",
            f"Question {index + 1} is too short or empty.",
        )
    if len(explanation) < 20:
        raise ValidationError(
            "AI_QUESTION_INVALID",
            f"Question {index + 1} is missing a real explanation grounded in the source.",
        )
    if not isinstance(options, list):
        raise ValidationError(
            "AI_QUESTION_INVALID",
            f"Question {index + 1} has malformed options.",
            status_code=400,
        )

    assert_no_placeholders(prompt, field=f"question[{index}].prompt")
    assert_no_placeholders(explanation, field=f"question[{index}].explanation")

    snapshots: list[OptionSnapshot] = []
    for opt_i, raw in enumerate(options):
        if not isinstance(raw, dict):
            raise ValidationError(
                "AI_QUESTION_INVALID",
                f"Question {index + 1} has a malformed option.",
                status_code=400,
            )
        text = str(raw.get("text") or "").strip()
        if text:
            assert_no_placeholders(text, field=f"question[{index}].option[{opt_i}]")
        snapshots.append(
            OptionSnapshot(
                text=text,
                is_correct=bool(raw.get("isCorrect") or raw.get("is_correct")),
            )
        )

    if kind in {"multiple_correct", "multi"}:
        messages: list[str] = []
        if len(snapshots) != 4:
            messages.append(MCQ_EXACTLY_FOUR)
        if any(not s.text.strip() for s in snapshots):
            messages.append(MCQ_ALL_FILLED)
        lowered = [s.text.strip().lower() for s in snapshots if s.text.strip()]
        if len(lowered) != len(set(lowered)):
            messages.append(MCQ_DUPLICATES)
        correct = sum(1 for s in snapshots if s.is_correct and s.text.strip())
        if correct < 2:
            messages.append("Multiple-correct questions need at least two correct options.")
        if messages:
            raise ValidationError(
                "AI_QUESTION_INVALID",
                messages[0],
                details=[
                    {"field": f"question[{index}].options", "message": m} for m in messages
                ],
                status_code=400,
            )
        return

    if is_true_false_options(snapshots) or kind in {"true_false", "true/false", "tf"}:
        correct = sum(1 for s in snapshots if s.is_correct)
        if correct == 0:
            raise ValidationError(
                "AI_QUESTION_INVALID",
                MCQ_SELECT_CORRECT,
                details=[{"field": f"question[{index}].options", "message": MCQ_SELECT_CORRECT}],
                status_code=400,
            )
        if correct > 1:
            raise ValidationError(
                "AI_QUESTION_INVALID",
                MCQ_ONE_CORRECT,
                details=[{"field": f"question[{index}].options", "message": MCQ_ONE_CORRECT}],
                status_code=400,
            )
        return

    assert_mcq_options_valid(
        snapshots,
        field=f"question[{index}].options",
        code="AI_QUESTION_INVALID",
    )


def validate_questions_batch(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not questions:
        raise ValidationError(
            "AI_GENERATION_EMPTY",
            "The AI returned no questions. Please retry.",
        )
    cleaned: list[dict[str, Any]] = []
    seen_prompts: set[str] = set()
    for idx, item in enumerate(questions):
        if not isinstance(item, dict):
            raise ValidationError("AI_QUESTION_INVALID", f"Question {idx + 1} is not an object.")
        validate_question_payload(item, index=idx)
        prompt_key = str(item.get("promptText") or item.get("prompt_text") or "").strip().lower()
        if prompt_key in seen_prompts:
            raise ValidationError(
                "AI_QUESTION_INVALID",
                f"Question {idx + 1} duplicates an earlier prompt.",
            )
        seen_prompts.add(prompt_key)
        cleaned.append(item)
    return cleaned


def validate_section_name(name: str, *, allow_generic: bool = True) -> None:
    cleaned = (name or "").strip()
    if len(cleaned) < 2:
        raise ValidationError("AI_STRUCTURE_EMPTY", "A section name was empty.")
    assert_no_placeholders(cleaned, field="section.name")
    if not allow_generic and _GENERIC_SECTION_ONLY.match(cleaned):
        raise ValidationError(
            "AI_STRUCTURE_GENERIC",
            f"Section name '{cleaned}' looks generic and was rejected for document mode.",
        )
