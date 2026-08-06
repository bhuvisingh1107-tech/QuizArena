"""Deterministic mock AI provider — TESTS ONLY (APP_ENV=test).

Produces content grounded in the prompt's source/topic text.
Never emits banned placeholder phrases (concept #, Distractor A, etc.).
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from typing import Any

from app.config import Settings
from app.services.ai.provider import AiProvider, ChatMessage, parse_json_object

logger = logging.getLogger(__name__)

_STOP = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "have",
    "are",
    "was",
    "were",
    "will",
    "into",
    "your",
    "about",
    "when",
    "what",
    "which",
    "their",
    "there",
    "then",
    "than",
    "also",
    "such",
    "only",
    "over",
    "under",
    "after",
    "before",
    "between",
    "section",
    "summary",
    "concepts",
    "language",
    "difficulty",
    "allowed",
    "kinds",
    "return",
    "json",
    "source",
    "excerpt",
    "generate",
    "questions",
    "topic",
    "create",
    "outline",
}


class MockAiProvider(AiProvider):
    name = "mock"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def chat_json(self, messages: list[ChatMessage], *, temperature: float = 0.3) -> dict[str, Any]:
        logger.info("LLM request provider=mock messages=%s", len(messages))
        user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        system = next((m.content for m in messages if m.role == "system"), "")

        if "section outline for the topic" in user.lower() or "trustedSources" in user:
            topic = _extract_quoted(user) or "General Topic"
            sections = _topic_sections(topic)
            key = topic.lower().strip()
            focused = topic
            if key in {"math", "maths", "mathematics"}:
                focused = "Algebra"
            elif key in {"general knowledge", "gk"}:
                focused = "World Geography"
            logger.info("mock topic outline sections=%s focused=%s", len(sections), focused)
            return {
                "title": f"{focused} Quiz",
                "focusedSubtopic": focused,
                "sections": sections,
                "trustedSources": [
                    {
                        "title": f"{focused} — Overview",
                        "url": f"https://en.wikipedia.org/wiki/{focused.replace(' ', '_')}",
                        "publisher": "Wikipedia",
                    }
                ],
            }

        if "produce a section outline" in user.lower() or "Analyze the following study" in user:
            title = _guess_title(user)
            sections = _sections_from_text(user)
            logger.info("mock document outline sections=%s", len(sections))
            return {"title": title, "sections": sections}

        if "Generate" in user and "questions for section" in user:
            section = _extract_between(user, 'section "', '"') or "General"
            count = _extract_count(user) or 3
            kinds = _extract_kinds(user)
            source = user.split("Source excerpt:", 1)[-1] if "Source excerpt:" in user else user
            questions = [
                _grounded_question(section, i, kinds[i % len(kinds)], source) for i in range(count)
            ]
            logger.info("mock questions generated=%s section=%s", len(questions), section)
            return {"questions": questions}

        if "regenerate" in system.lower() or "regenerate" in user.lower():
            source = user
            section = _extract_between(user, "about ", ".") or "Topic"
            return {"question": _grounded_question(section, 0, "mcq", source)}

        try:
            return parse_json_object(user)
        except Exception as exc:
            raise ValueError(
                "Mock provider could not parse JSON and will not invent empty quizzes"
            ) from exc

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


def _terms_from(text: str, *, limit: int = 12) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", text or "")
    terms: list[str] = []
    seen: set[str] = set()
    for word in words:
        key = word.lower()
        if key in _STOP or key in seen:
            continue
        seen.add(key)
        terms.append(word)
        if len(terms) >= limit:
            break
    return terms or ["Scheduling", "Memory", "Process", "Throughput"]


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
            "Processes and Threads",
            "CPU Scheduling",
            "Memory Management",
            "Virtual Memory",
            "File Systems",
            "Concurrency and Synchronization",
        ],
        "vector calculus": [
            "Vectors and Vector Fields",
            "Gradient",
            "Divergence",
            "Curl",
            "Line and Surface Integrals",
            "Applications of Stokes and Divergence Theorems",
        ],
        "computer networks": [
            "Network Models",
            "Physical Layer",
            "Data Link Layer",
            "Network Layer",
            "Transport Layer",
            "Application Layer",
        ],
        "machine learning": [
            "Supervised Learning",
            "Unsupervised Learning",
            "Model Evaluation",
            "Overfitting and Regularization",
            "Neural Networks",
            "Feature Engineering",
        ],
        # Broad topics narrow to a coherent subtopic (mirrors topic_focus guidance).
        "math": [
            "Linear Equations",
            "Quadratic Equations",
            "Inequalities",
            "Systems of Equations",
        ],
        "maths": [
            "Linear Equations",
            "Quadratic Equations",
            "Inequalities",
            "Systems of Equations",
        ],
        "mathematics": [
            "Linear Equations",
            "Quadratic Equations",
            "Inequalities",
            "Systems of Equations",
        ],
        "general knowledge": [
            "Continents and Oceans",
            "World Capitals",
            "Major Landmarks",
            "Climate Zones",
        ],
        "gk": [
            "Continents and Oceans",
            "World Capitals",
            "Major Landmarks",
            "Climate Zones",
        ],
    }
    key = topic.lower().strip()
    names = presets.get(key)
    focused = topic
    if names:
        if key in {"math", "maths", "mathematics"}:
            focused = "Algebra"
        elif key in {"general knowledge", "gk"}:
            focused = "World Geography"
    else:
        # Derive section-like phrases from the topic words — avoid bare Foundations/Applications.
        parts = [p for p in re.split(r"[\s,/]+", topic) if len(p) > 2]
        if len(parts) >= 2:
            names = [
                f"{parts[0]} Fundamentals",
                f"{parts[-1]} Methods",
                f"{topic} Problem Solving",
                f"{topic} Worked Examples",
            ]
        else:
            names = [
                f"{topic} Fundamentals",
                f"{topic} Methods",
                f"{topic} Problem Solving",
                f"{topic} Worked Examples",
            ]
    return [
        {
            "name": name,
            "summary": (
                f"{name} is a core unit within {focused}. Students learn definitions, "
                f"standard notation, worked relationships, and typical exam reasoning for {name}. "
                f"Key relationships connect {name} to neighbouring ideas in {focused}, "
                f"including how to apply the ideas to short problems and identify common mistakes."
            ),
            "concepts": [name, focused, topic],
        }
        for name in names
    ]


def _sections_from_text(user: str) -> list[dict[str, Any]]:
    body = user.split("Source material:", 1)[-1]
    headings = re.findall(
        r"^(?:Chapter\s+\d+[:.\s]+|[0-9]+\.\s+|##\s+|#\s+)(.+)$",
        body,
        flags=re.M | re.I,
    )
    if not headings:
        headings = [
            line.strip("# ").strip()
            for line in body.splitlines()
            if line.strip().startswith("#")
        ]
    if not headings:
        headings = [
            line.strip()
            for line in body.splitlines()
            if line.strip()
            and line.strip() == line.strip().title()
            and 3 < len(line.strip()) < 60
        ][:8]
    if not headings:
        terms = _terms_from(body, limit=4)
        headings = [f"{t} Overview" for t in terms]
    # Avoid bare generic section titles rejected in document mode.
    generic = {
        "introduction",
        "foundations",
        "core ideas",
        "applications",
        "core concepts",
        "practice",
    }
    named: list[str] = []
    for h in headings:
        title = h.strip()[:120]
        if title.lower() in generic:
            terms = _terms_from(body, limit=2)
            suffix = terms[0] if terms else "Material"
            title = f"{title} — {suffix}"
        named.append(title)
    return [
        {
            "name": h,
            "summary": f"Material covering {h} from the uploaded source.",
            "concepts": [h],
        }
        for h in named
    ]


def _grounded_question(section: str, index: int, kind: str, source: str) -> dict[str, Any]:
    """Build a non-placeholder question tied to terms in the source/section."""
    kind = kind if kind in {"mcq", "multiple_correct", "true_false", "fill_blank"} else "mcq"
    terms = _terms_from(f"{section}\n{source}", limit=16)
    focus = terms[index % len(terms)]
    alt = terms[(index + 1) % len(terms)]
    alt2 = terms[(index + 2) % len(terms)]
    alt3 = terms[(index + 3) % len(terms)]

    if kind == "true_false":
        prompt = f"True or False: In {section}, {focus} is discussed as part of the material."
        options = [
            {"text": "True", "isCorrect": True},
            {"text": "False", "isCorrect": False},
        ]
    elif kind == "multiple_correct":
        prompt = f"Which of the following are relevant to {focus} within {section}? (Select all that apply.)"
        options = [
            {"text": f"{focus} is covered under {section}", "isCorrect": True},
            {"text": f"{alt} can relate to the same {section} discussion", "isCorrect": True},
            {"text": f"{alt2} replaces all of {section}", "isCorrect": False},
            {"text": f"{section} never mentions {focus}", "isCorrect": False},
        ]
    elif kind == "fill_blank":
        prompt = f"In {section}, the term that best completes the idea around {focus} is ____."
        options = [
            {"text": focus, "isCorrect": True},
            {"text": alt, "isCorrect": False},
            {"text": alt2, "isCorrect": False},
            {"text": alt3, "isCorrect": False},
        ]
    else:
        prompt = f"In {section}, which statement about {focus} is best supported by the material?"
        options = [
            {"text": f"{focus} is a key idea presented in {section}", "isCorrect": True},
            {"text": f"{focus} is never related to {section}", "isCorrect": False},
            {"text": f"{alt} fully replaces the role of {focus}", "isCorrect": False},
            {"text": f"{section} only covers {alt3} and ignores {focus}", "isCorrect": False},
        ]

    return {
        "kind": kind,
        "promptText": prompt,
        "explanation": (
            f"The source material for {section} references {focus}; "
            f"the chosen answer matches that coverage rather than contradicting it."
        ),
        "difficulty": ["easy", "medium", "hard"][index % 3],
        "topicLabel": section,
        "estimatedTimeSeconds": 25,
        "sourceLocator": f"Section: {section}",
        "options": options,
    }
