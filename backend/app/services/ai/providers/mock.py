"""Deterministic mock AI provider for tests and offline development."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any

from app.config import Settings
from app.services.ai.provider import AiProvider, ChatMessage, parse_json_object


class MockAiProvider(AiProvider):
    name = "mock"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def chat_json(self, messages: list[ChatMessage], *, temperature: float = 0.3) -> dict[str, Any]:
        import logging

        logger = logging.getLogger(__name__)
        logger.info("LLM request provider=mock messages=%s", len(messages))
        user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        system = next((m.content for m in messages if m.role == "system"), "")

        if "section outline for the topic" in user.lower() or "trustedSources" in user:
            topic = _extract_quoted(user) or "General Topic"
            sections = _topic_sections(topic)
            return {
                "title": f"{topic} Quiz",
                "sections": sections,
                "trustedSources": [
                    {
                        "title": f"{topic} — Overview",
                        "url": f"https://en.wikipedia.org/wiki/{topic.replace(' ', '_')}",
                        "publisher": "Wikipedia",
                    }
                ],
            }

        if "produce a section outline" in user.lower() or "Analyze the following study" in user:
            title = _guess_title(user)
            sections = _sections_from_text(user)
            return {"title": title, "sections": sections}

        if "Generate" in user and "questions for section" in user:
            section = _extract_between(user, 'section "', '"') or "General"
            count = _extract_count(user) or 3
            kinds = _extract_kinds(user)
            return {
                "questions": [
                    _mock_question(section, i, kinds[i % len(kinds)]) for i in range(count)
                ]
            }

        if "regenerate" in system.lower() or "regenerate" in user.lower():
            return _mock_question("Regenerated", 0, "mcq")

        # Fallback parse attempt (tests may inject JSON).
        try:
            return parse_json_object(user)
        except Exception:
            return {"title": "Generated Quiz", "sections": [], "questions": []}

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            vals = [((digest[i % len(digest)] / 255.0) * 2 - 1) for i in range(32)]
            norm = math.sqrt(sum(v * v for v in vals)) or 1.0
            vectors.append([v / norm for v in vals])
        return vectors


def _extract_quoted(text: str) -> str | None:
    match = re.search(r'"([^"]+)"', text)
    return match.group(1).strip() if match else None


def _extract_between(text: str, start: str, end: str) -> str | None:
    i = text.find(start)
    if i < 0:
        return None
    i += len(start)
    j = text.find(end, i)
    if j < 0:
        return None
    return text[i:j].strip()


def _extract_count(text: str) -> int | None:
    match = re.search(r"Generate\s+(\d+)\s+questions", text, re.I)
    return int(match.group(1)) if match else None


def _extract_kinds(text: str) -> list[str]:
    match = re.search(r"Allowed kinds:\s*([^\n]+)", text)
    if not match:
        return ["mcq"]
    raw = match.group(1)
    kinds = [k.strip() for k in re.split(r"[,|]", raw) if k.strip()]
    return kinds or ["mcq"]


def _guess_title(user: str) -> str:
    hint = re.search(r"title hint:\s*([^\n]+)", user, re.I)
    if hint and hint.group(1).strip() and hint.group(1).strip().lower() != "none":
        return hint.group(1).strip()[:120]
    return "Study Material Quiz"


def _topic_sections(topic: str) -> list[dict[str, Any]]:
    presets = {
        "basic geometry": [
            "Points",
            "Lines",
            "Angles",
            "Triangles",
            "Quadrilaterals",
            "Circles",
            "Polygons",
        ],
        "operating systems": [
            "Introduction",
            "Processes",
            "Memory Management",
            "File Systems",
            "Concurrency",
            "Scheduling",
        ],
        "computer networks": [
            "Network Models",
            "Physical Layer",
            "Data Link",
            "Network Layer",
            "Transport Layer",
            "Application Layer",
        ],
    }
    names = presets.get(topic.lower())
    if not names:
        names = [f"{topic} Foundations", f"{topic} Core Ideas", f"{topic} Applications"]
    return [
        {
            "name": name,
            "summary": f"Key ideas in {name} for {topic}.",
            "concepts": [name, topic],
        }
        for name in names
    ]


def _sections_from_text(user: str) -> list[dict[str, Any]]:
    body = user.split("Source material:", 1)[-1]
    headings = re.findall(
        r"^(?:Chapter\s+\d+[:.\s]+|[0-9]+\.\s+|#\s+)(.+)$",
        body,
        flags=re.M | re.I,
    )
    if not headings:
        # Fall back to capitalized lines as crude section hints.
        headings = [
            line.strip()
            for line in body.splitlines()
            if line.strip() and line.strip() == line.strip().title() and 3 < len(line.strip()) < 60
        ][:8]
    if not headings:
        headings = ["Introduction", "Core Concepts", "Practice"]
    return [
        {
            "name": h[:120],
            "summary": f"Coverage of {h}.",
            "concepts": [h],
        }
        for h in headings
    ]


def _mock_question(section: str, index: int, kind: str) -> dict[str, Any]:
    kind = kind if kind in {"mcq", "multiple_correct", "true_false", "fill_blank"} else "mcq"
    prompt = f"In {section}, which statement best describes concept #{index + 1}?"
    if kind == "true_false":
        options = [
            {"text": "True", "isCorrect": True},
            {"text": "False", "isCorrect": False},
        ]
    elif kind == "multiple_correct":
        options = [
            {"text": f"{section} idea A", "isCorrect": True},
            {"text": f"{section} idea B", "isCorrect": True},
            {"text": "Unrelated claim", "isCorrect": False},
            {"text": "Contradictory claim", "isCorrect": False},
        ]
    elif kind == "fill_blank":
        options = [
            {"text": f"{section}-term", "isCorrect": True},
            {"text": "Placeholder", "isCorrect": False},
            {"text": "Noise", "isCorrect": False},
            {"text": "Distractor", "isCorrect": False},
        ]
        prompt = f"Fill in the blank: The key term for {section} #{index + 1} is ____."
    else:
        options = [
            {"text": f"Correct {section} fact", "isCorrect": True},
            {"text": "Plausible distractor A", "isCorrect": False},
            {"text": "Plausible distractor B", "isCorrect": False},
            {"text": "Plausible distractor C", "isCorrect": False},
        ]
    return {
        "kind": kind,
        "promptText": prompt,
        "explanation": f"This checks understanding of {section}.",
        "difficulty": ["easy", "medium", "hard"][index % 3],
        "topicLabel": section,
        "estimatedTimeSeconds": 20,
        "sourceLocator": f"Section: {section}",
        "options": options,
    }
