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
