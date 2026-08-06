"""Detect broad quiz topics and guide the outline model toward a focused subtopic.

Topic-mode generation does not fetch web pages. The LLM outline summaries become the
only "source excerpt" for question generation. Broad topics like "Math" or
"General Knowledge" tend to produce thin, generic summaries — which in turn cause
placeholder explanations. Narrowing first keeps the synthetic source concrete.
"""

from __future__ import annotations

import re

# Single-word / catch-all subjects that sprawl too widely for a coherent quiz.
_BROAD_TOPICS: frozenset[str] = frozenset(
    {
        "math",
        "maths",
        "mathematics",
        "science",
        "physics",
        "chemistry",
        "biology",
        "history",
        "geography",
        "english",
        "literature",
        "computer science",
        "cs",
        "programming",
        "general knowledge",
        "gk",
        "trivia",
        "current affairs",
        "social studies",
        "arts",
        "business",
        "economics",
        "engineering",
        "technology",
        "tech",
        "sports",
        "music",
        "philosophy",
        "psychology",
        "sociology",
        "politics",
        "civics",
        "environment",
        "astronomy",
        "earth science",
        "life science",
        "natural science",
        "world history",
        "world geography",
        "general science",
        "basic math",
        "basic maths",
        "basic mathematics",
    }
)

_BROAD_EXAMPLES: dict[str, str] = {
    "math": "Algebra (linear equations and quadratic equations)",
    "maths": "Algebra (linear equations and quadratic equations)",
    "mathematics": "Algebra (linear equations and quadratic equations)",
    "basic math": "Fractions and decimals",
    "basic maths": "Fractions and decimals",
    "basic mathematics": "Fractions and decimals",
    "science": "Physics — Newton's laws of motion",
    "physics": "Newtonian mechanics (forces and motion)",
    "chemistry": "Atomic structure and the periodic table",
    "biology": "Cell structure and function",
    "history": "World War II — major causes and turning points",
    "geography": "World Geography — continents, oceans, and climate zones",
    "world geography": "Physical geography of continents and oceans",
    "world history": "Ancient civilizations of Mesopotamia and Egypt",
    "general knowledge": "World Geography — capitals, landmarks, and continents",
    "gk": "World Geography — capitals, landmarks, and continents",
    "trivia": "World Geography — capitals, landmarks, and continents",
    "current affairs": "United Nations and international organizations",
    "computer science": "Data structures — arrays, stacks, and queues",
    "cs": "Data structures — arrays, stacks, and queues",
    "programming": "Python fundamentals — variables, loops, and functions",
    "english": "English grammar — parts of speech and sentence structure",
    "literature": "Shakespeare — key plays and themes",
    "economics": "Supply and demand in microeconomics",
    "business": "Marketing mix (4Ps)",
    "engineering": "Basic electrical circuits (Ohm's law)",
    "technology": "Computer networks — OSI and TCP/IP models",
    "tech": "Computer networks — OSI and TCP/IP models",
    "sports": "Olympic Games — history and major sports",
    "music": "Western classical music — eras and forms",
    "philosophy": "Ethics — utilitarianism and deontology",
    "psychology": "Classical and operant conditioning",
    "astronomy": "Solar system planets and orbits",
    "environment": "Climate change — greenhouse gases and impacts",
}


def normalize_topic(topic: str) -> str:
    cleaned = re.sub(r"\s+", " ", (topic or "").strip().lower())
    cleaned = re.sub(r"[^\w\s/+&-]", "", cleaned)
    return cleaned.strip()


def is_broad_topic(topic: str) -> bool:
    """Return True when the topic is too broad for a single coherent quiz."""
    key = normalize_topic(topic)
    if not key:
        return False
    if key in _BROAD_TOPICS:
        return True
    # Very short single-token subjects are usually broad ("Art", "Law").
    tokens = key.split()
    if len(tokens) == 1 and len(key) <= 12 and key not in {
        "calculus",
        "algebra",
        "geometry",
        "trigonometry",
        "statistics",
        "probability",
        "thermodynamics",
        "optics",
        "genetics",
        "anatomy",
        "ecology",
        "networking",
        "databases",
        "algorithms",
        "cybersecurity",
    }:
        # Only treat as broad if it looks like a school subject word.
        return key in _BROAD_TOPICS or key.endswith("ics") or key.endswith("ology")
    return False


def suggested_subtopic_example(topic: str) -> str:
    key = normalize_topic(topic)
    if key in _BROAD_EXAMPLES:
        return _BROAD_EXAMPLES[key]
    title = topic.strip() or "the topic"
    return f"one concrete, teachable subtopic within {title}"


def topic_narrowing_instruction(topic: str) -> str:
    """Instruction block injected into the topic-outline user prompt when needed."""
    if not is_broad_topic(topic):
        return (
            "The topic looks specific enough. Keep the outline tightly focused on it. "
            "Do not widen into unrelated areas."
        )
    example = suggested_subtopic_example(topic)
    return (
        f'The supplied topic "{topic.strip()}" is BROAD. '
        "Before outlining sections, first choose ONE coherent, exam-ready subtopic "
        f'(example: "{example}") and generate the entire outline and all sections '
        "from that single subtopic only. Put the chosen subtopic in the quiz title. "
        "Do not try to cover the whole broad field."
    )
