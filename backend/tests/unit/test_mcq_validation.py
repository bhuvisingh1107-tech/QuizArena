"""Unit tests for strict MCQ option validation."""

from __future__ import annotations

import pytest

from app.core.exceptions import ValidationError
from app.services.mcq_validation import (
    MCQ_ALL_FILLED,
    MCQ_DUPLICATES,
    MCQ_EXACTLY_FOUR,
    MCQ_ONE_CORRECT,
    MCQ_SELECT_CORRECT,
    OptionSnapshot,
    assert_mcq_options_valid,
    collect_mcq_option_errors,
)


def _opts(*pairs: tuple[str, bool]) -> list[OptionSnapshot]:
    return [OptionSnapshot(text=text, is_correct=correct) for text, correct in pairs]


def test_valid_four_option_mcq() -> None:
    errors = collect_mcq_option_errors(
        _opts(
            ("Paris", True),
            ("Lyon", False),
            ("Marseille", False),
            ("Nice", False),
        )
    )
    assert errors == []


def test_three_options() -> None:
    errors = collect_mcq_option_errors(
        _opts(("A", True), ("B", False), ("C", False))
    )
    assert MCQ_EXACTLY_FOUR in errors


def test_five_options() -> None:
    errors = collect_mcq_option_errors(
        _opts(
            ("A", True),
            ("B", False),
            ("C", False),
            ("D", False),
            ("E", False),
        )
    )
    assert MCQ_EXACTLY_FOUR in errors


def test_blank_option() -> None:
    errors = collect_mcq_option_errors(
        _opts(("A", True), ("", False), ("C", False), ("D", False))
    )
    assert MCQ_ALL_FILLED in errors


def test_duplicate_options() -> None:
    errors = collect_mcq_option_errors(
        _opts(("Paris", True), ("paris", False), ("Lyon", False), ("Nice", False))
    )
    assert MCQ_DUPLICATES in errors


def test_no_correct_answer() -> None:
    errors = collect_mcq_option_errors(
        _opts(("A", False), ("B", False), ("C", False), ("D", False))
    )
    assert MCQ_SELECT_CORRECT in errors


def test_multiple_correct_answers() -> None:
    errors = collect_mcq_option_errors(
        _opts(("A", True), ("B", True), ("C", False), ("D", False))
    )
    assert MCQ_ONE_CORRECT in errors


def test_assert_raises_http_400() -> None:
    with pytest.raises(ValidationError) as exc:
        assert_mcq_options_valid(_opts(("A", True), ("B", False)))
    assert exc.value.status_code == 400
    assert exc.value.code == "MCQ_INVALID"
    assert MCQ_EXACTLY_FOUR in exc.value.message


def test_true_false_valid() -> None:
    assert collect_mcq_option_errors(_opts(("True", True), ("False", False))) == []
