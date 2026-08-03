"""Prompt templates for AI quiz generation (never hardcode in service code)."""

from __future__ import annotations

from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompt_files"


def load_prompt(name: str) -> str:
    path = _PROMPTS_DIR / f"{name}.txt"
    if not path.is_file():
        raise FileNotFoundError(f"AI prompt template missing: {name}")
    return path.read_text(encoding="utf-8").strip()


STRUCTURE_SYSTEM = "structure_system"
STRUCTURE_USER = "structure_user"
QUESTIONS_SYSTEM = "questions_system"
QUESTIONS_USER = "questions_user"
REGENERATE_QUESTION_SYSTEM = "regenerate_question_system"
TOPIC_OUTLINE_SYSTEM = "topic_outline_system"
TOPIC_OUTLINE_USER = "topic_outline_user"
