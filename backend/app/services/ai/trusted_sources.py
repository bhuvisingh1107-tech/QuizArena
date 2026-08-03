"""Trusted educational source helpers for topic-mode generation."""

from __future__ import annotations

from urllib.parse import quote

TRUSTED_PUBLISHERS = (
    "Wikipedia",
    "Khan Academy",
    "MIT OpenCourseWare",
    "NPTEL",
    "Britannica",
    "NASA",
    "WHO",
)


def trusted_source_seeds(topic: str) -> list[dict[str, str]]:
    """Return canonical reference URLs (fetch may be added later; attribution always stored)."""
    slug = quote(topic.replace(" ", "_"))
    encoded = quote(topic)
    return [
        {
            "title": f"{topic} — Wikipedia",
            "url": f"https://en.wikipedia.org/wiki/{slug}",
            "publisher": "Wikipedia",
        },
        {
            "title": f"{topic} — Khan Academy search",
            "url": f"https://www.khanacademy.org/search?page_search_query={encoded}",
            "publisher": "Khan Academy",
        },
        {
            "title": f"{topic} — MIT OCW search",
            "url": f"https://ocw.mit.edu/search/?q={encoded}",
            "publisher": "MIT OpenCourseWare",
        },
        {
            "title": f"{topic} — Britannica search",
            "url": f"https://www.britannica.com/search?query={encoded}",
            "publisher": "Britannica",
        },
    ]
