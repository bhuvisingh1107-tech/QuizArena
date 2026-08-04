"""Strict MCQ option rules shared by builder publish, option CRUD, and AI save."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from app.core.exceptions import ValidationError

MCQ_OPTION_COUNT = 4

MSG_EXACTLY_FOUR = "MCQ must contain exactly 4 options."
MSG_ALL_FILLED = "All options must be filled."
MSG_ONLY_ONE_CORRECT = "Only one option can be marked correct."
MSG_SELECT_CORRECT = "Please select the correct answer."
MSG_DUPLICATES = "Duplicate options are not allowed."
MSG_LAST_SECTION = "A quiz must contain at least one section"

# Aliases used by unit tests / older call sites
MCQ_EXACTLY_FOUR = MSG_EXACTLY_FOUR
MCQ_ALL_FILLED = MSG_ALL_FILLED
MCQ_ONE_CORRECT = MSG_ONLY_ONE_CORRECT
MCQ_SELECT_CORRECT = MSG_SELECT_CORRECT
MCQ_DUPLICATES = MSG_DUPLICATES


@dataclass(frozen=True)
class OptionSnapshot:
    text: str
    is_correct: bool


def is_true_false_options(options: Iterable[OptionSnapshot | tuple[str, bool]]) -> bool:
    texts: list[str] = []
    for item in options:
        if isinstance(item, OptionSnapshot):
            texts.append(item.text)
        else:
            texts.append(item[0])
    cleaned = sorted(t.strip().lower() for t in texts)
    return len(cleaned) == 2 and cleaned == ["false", "true"]


def _as_snapshots(
    options: list[OptionSnapshot] | list[tuple[str, bool]],
) -> list[OptionSnapshot]:
    out: list[OptionSnapshot] = []
    for item in options:
        if isinstance(item, OptionSnapshot):
            out.append(item)
        else:
            out.append(OptionSnapshot(text=item[0], is_correct=bool(item[1])))
    return out


def mcq_validation_messages(
    options: list[OptionSnapshot] | list[tuple[str, bool]],
    *,
    require_exact_count: bool = True,
    allow_multiple_correct: bool = False,
) -> list[str]:
    """Return human-readable MCQ validation messages (empty = valid)."""
    snaps = _as_snapshots(options)
    messages: list[str] = []

    if is_true_false_options(snaps):
        if any(not s.text.strip() for s in snaps):
            messages.append(MSG_ALL_FILLED)
        correct = sum(1 for s in snaps if s.is_correct)
        if correct == 0:
            messages.append(MSG_SELECT_CORRECT)
        elif correct > 1:
            messages.append(MSG_ONLY_ONE_CORRECT)
        return messages

    if require_exact_count:
        if len(snaps) != MCQ_OPTION_COUNT:
            messages.append(MSG_EXACTLY_FOUR)
    elif len(snaps) > MCQ_OPTION_COUNT:
        messages.append(MSG_EXACTLY_FOUR)

    if any(not s.text.strip() for s in snaps):
        messages.append(MSG_ALL_FILLED)

    lowered = [s.text.strip().lower() for s in snaps if s.text.strip()]
    if len(lowered) != len(set(lowered)):
        messages.append(MSG_DUPLICATES)

    correct = sum(1 for s in snaps if s.is_correct)
    if require_exact_count and correct == 0:
        messages.append(MSG_SELECT_CORRECT)
    elif correct > 1 and not allow_multiple_correct:
        messages.append(MSG_ONLY_ONE_CORRECT)

    seen: set[str] = set()
    unique: list[str] = []
    for msg in messages:
        if msg not in seen:
            seen.add(msg)
            unique.append(msg)
    return unique


def collect_mcq_option_errors(options: list[OptionSnapshot]) -> list[str]:
    """Ready-checklist helper used by QuizService (always single-correct MCQ)."""
    return mcq_validation_messages(
        options,
        require_exact_count=True,
        allow_multiple_correct=False,
    )


def validate_mcq_options(
    options: list[OptionSnapshot] | list[tuple[str, bool]],
    *,
    require_exact_count: bool = True,
    allow_multiple_correct: bool = False,
) -> None:
    """Raise HTTP 400 ValidationError if options violate MCQ rules."""
    assert_mcq_options_valid(
        _as_snapshots(options),
        require_exact_count=require_exact_count,
        allow_multiple_correct=allow_multiple_correct,
    )


def assert_mcq_options_valid(
    options: list[OptionSnapshot] | list[tuple[str, bool]],
    *,
    field: str = "options",
    code: str = "MCQ_INVALID",
    require_exact_count: bool = True,
    allow_multiple_correct: bool = False,
) -> None:
    """Raise HTTP 400 ValidationError if options violate MCQ rules."""
    messages = mcq_validation_messages(
        options,
        require_exact_count=require_exact_count,
        allow_multiple_correct=allow_multiple_correct,
    )
    if not messages:
        return
    raise ValidationError(
        code,
        messages[0],
        details=[{"field": field, "message": m} for m in messages],
        status_code=400,
    )


def options_from_orm(raw_options: Iterable[Any]) -> list[OptionSnapshot]:
    from app.services.question_crypto import open_option_fields

    opened: list[OptionSnapshot] = []
    for opt in raw_options:
        text, is_correct = open_option_fields(opt.text, opt.is_correct)
        opened.append(OptionSnapshot(text=text or "", is_correct=bool(is_correct)))
    return opened


def options_from_payload(raw_options: list[Any]) -> list[OptionSnapshot]:
    opened: list[OptionSnapshot] = []
    for raw in raw_options:
        if not isinstance(raw, dict):
            opened.append(OptionSnapshot(text="", is_correct=False))
            continue
        text = str(raw.get("text") or "")
        is_correct = bool(raw.get("isCorrect") or raw.get("is_correct"))
        opened.append(OptionSnapshot(text=text, is_correct=is_correct))
    return opened
