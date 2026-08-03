"""Seal / open question and option content for at-rest AES-GCM encryption."""

from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.core.crypto import (
    is_sealed,
    maybe_open_text,
    maybe_seal_text,
    open_json,
    seal_json,
)


def _key(settings: Settings | None = None) -> str | None:
    cfg = settings or get_settings()
    key = (cfg.question_encryption_key or "").strip()
    return key or None


def seal_prompt(text: str | None, settings: Settings | None = None) -> str | None:
    return maybe_seal_text(text, _key(settings))


def open_prompt(text: str | None, settings: Settings | None = None) -> str | None:
    return maybe_open_text(text, _key(settings))


def seal_explanation(text: str | None, settings: Settings | None = None) -> str | None:
    return maybe_seal_text(text, _key(settings))


def open_explanation(text: str | None, settings: Settings | None = None) -> str | None:
    return maybe_open_text(text, _key(settings))


def seal_option_fields(
    text: str,
    is_correct: bool,
    settings: Settings | None = None,
) -> tuple[str, bool]:
    """When a key is configured, store option text+correctness in sealed JSON.

    ``is_correct`` column is forced to False as a decoy so DB dumps never reveal
    the answer bit; the real flag lives only inside the ciphertext.
    """
    key = _key(settings)
    if not key:
        return text, is_correct
    if is_sealed(text):
        # Already sealed — keep decoy False
        return text, False
    sealed = seal_json({"text": text, "is_correct": bool(is_correct)}, key)
    return sealed, False


def open_option_fields(
    text: str,
    is_correct: bool,
    settings: Settings | None = None,
) -> tuple[str, bool]:
    key = _key(settings)
    if is_sealed(text):
        data = open_json(text, key)
        return str(data.get("text") or ""), bool(data.get("is_correct"))
    return text, is_correct


def decrypt_question_dict(
    *,
    prompt_text: str | None,
    explanation: str | None,
    options: list[dict[str, Any]],
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Return plaintext prompt/explanation/options for internal use only."""
    opened_options = []
    for opt in options:
        plain_text, plain_correct = open_option_fields(
            str(opt.get("text") or ""),
            bool(opt.get("is_correct") or opt.get("isCorrect") or False),
            settings,
        )
        opened_options.append({**opt, "text": plain_text, "is_correct": plain_correct})
    return {
        "prompt_text": open_prompt(prompt_text, settings),
        "explanation": open_explanation(explanation, settings),
        "options": opened_options,
    }
