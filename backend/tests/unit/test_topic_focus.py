"""Tests for broad-topic narrowing helpers."""

from __future__ import annotations

from app.services.ai.topic_focus import (
    is_broad_topic,
    suggested_subtopic_example,
    topic_narrowing_instruction,
)


def test_detects_broad_topics() -> None:
    assert is_broad_topic("Math")
    assert is_broad_topic("Mathematics")
    assert is_broad_topic("General Knowledge")
    assert is_broad_topic("Science")
    assert is_broad_topic("GK")


def test_specific_topics_are_not_broad() -> None:
    assert not is_broad_topic("Vector Calculus")
    assert not is_broad_topic("Operating Systems")
    assert not is_broad_topic("Quadratic Equations")
    assert not is_broad_topic("CPU Scheduling")


def test_narrowing_instruction_for_broad_topic() -> None:
    text = topic_narrowing_instruction("Math")
    assert "BROAD" in text
    assert "subtopic" in text.lower()
    assert "Algebra" in suggested_subtopic_example("Math")


def test_narrowing_instruction_for_specific_topic() -> None:
    text = topic_narrowing_instruction("Vector Calculus")
    assert "BROAD" not in text
    assert "specific enough" in text.lower()
