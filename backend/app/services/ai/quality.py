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
    prompt = str(item.get("promptText") or item.get("prompt_text") or "").strip()
    explanation = str(item.get("explanation") or "").strip()
    options = item.get("options") or []

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
    if not isinstance(options, list) or len(options) < 2:
        raise ValidationError(
            "AI_QUESTION_INVALID",
            f"Question {index + 1} must include at least 2 options.",
        )

    assert_no_placeholders(prompt, field=f"question[{index}].prompt")
    assert_no_placeholders(explanation, field=f"question[{index}].explanation")

    correct = 0
    seen_texts: set[str] = set()
    for opt_i, raw in enumerate(options):
        if not isinstance(raw, dict):
            raise ValidationError(
                "AI_QUESTION_INVALID",
                f"Question {index + 1} has a malformed option.",
            )
        text = str(raw.get("text") or "").strip()
        if len(text) < 1:
            raise ValidationError(
                "AI_QUESTION_INVALID",
                f"Question {index + 1} has an empty option.",
            )
        assert_no_placeholders(text, field=f"question[{index}].option[{opt_i}]")
        key = text.lower()
        if key in seen_texts:
            raise ValidationError(
                "AI_QUESTION_INVALID",
                f"Question {index + 1} has duplicate option text.",
            )
        seen_texts.add(key)
        if raw.get("isCorrect") or raw.get("is_correct"):
            correct += 1

    if correct < 1:
        raise ValidationError(
            "AI_QUESTION_INVALID",
            f"Question {index + 1} has no correct option marked.",
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
