"""Unit tests for AI chunking + mock provider."""

from app.services.ai.chunking import chunk_text, normalize_text
from app.services.ai.provider import ChatMessage, get_ai_provider
from app.config import Settings


def test_normalize_and_chunk() -> None:
    raw = "Intro\n\n\nArrays are cool.\n\nLinked lists follow.\n"
    text = normalize_text(raw)
    assert "\n\n\n" not in text
    chunks = chunk_text(text, max_tokens=20, overlap_tokens=2)
    assert chunks
    assert chunks[0].index == 0


def test_mock_provider_topic_outline() -> None:
    provider = get_ai_provider(Settings(ai_provider="mock", app_env="test"))
    data = provider.chat_json(
        [
            ChatMessage("system", "outline"),
            ChatMessage(
                "user",
                'Create a section outline for the topic: "Basic Geometry"\nLanguage: en\n\nReturn JSON with trustedSources',
            ),
        ]
    )
    assert data["sections"]
    assert any(s["name"] == "Triangles" for s in data["sections"])
    embeds = provider.embed(["hello", "world"])
    assert len(embeds) == 2
    assert len(embeds[0]) == 32


def test_mock_questions_have_no_placeholders() -> None:
    from app.services.ai.quality import find_placeholder_hits

    provider = get_ai_provider(Settings(ai_provider="mock", app_env="test"))
    data = provider.chat_json(
        [
            ChatMessage("system", "questions"),
            ChatMessage(
                "user",
                'Generate 3 questions for section "CPU Scheduling".\n'
                "Allowed kinds: mcq\n"
                "Source excerpt:\n"
                "Round robin scheduling uses time slices. SJF minimizes average waiting time.\n",
            ),
        ]
    )
    for q in data["questions"]:
        blob = " ".join(
            [
                q["promptText"],
                q["explanation"],
                " ".join(o["text"] for o in q["options"]),
            ]
        )
        assert not find_placeholder_hits(blob), blob


def test_mock_broad_topic_math_narrows_and_validates() -> None:
    from app.services.ai.generation_service import AiGenerationService
    from app.services.ai.prompts import QUESTIONS_SYSTEM, QUESTIONS_USER, TOPIC_OUTLINE_USER, load_prompt
    from app.services.ai.provider import render_template
    from app.services.ai.quality import validate_questions_batch
    from app.services.ai.topic_focus import topic_narrowing_instruction

    provider = get_ai_provider(Settings(ai_provider="mock", app_env="test"))
    outline = provider.chat_json(
        [
            ChatMessage("system", "outline"),
            ChatMessage(
                "user",
                render_template(
                    load_prompt(TOPIC_OUTLINE_USER),
                    topic="Math",
                    language="en",
                    topic_focus_guidance=topic_narrowing_instruction("Math"),
                ),
            ),
        ]
    )
    assert outline["focusedSubtopic"] == "Algebra"
    assert "Algebra" in outline["title"]
    svc = object.__new__(AiGenerationService)
    synthetic = AiGenerationService._build_topic_source_text(svc, outline, "Math")
    assert len(synthetic) > 500
    section = outline["sections"][0]
    data = provider.chat_json(
        [
            ChatMessage("system", load_prompt(QUESTIONS_SYSTEM)),
            ChatMessage(
                "user",
                render_template(
                    load_prompt(QUESTIONS_USER),
                    question_count=2,
                    section_name=section["name"],
                    difficulty="medium",
                    question_kinds="mcq",
                    language="en",
                    section_summary=section["summary"],
                    concepts=", ".join(section["concepts"]),
                    source_text=synthetic,
                ),
            ),
        ]
    )
    validated = validate_questions_batch(data["questions"])
    assert len(validated) >= 2
    assert all(len(q["explanation"]) >= 20 for q in validated)