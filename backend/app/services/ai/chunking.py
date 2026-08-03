"""Text normalization and chunking for retrieval-augmented generation."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class TextChunk:
    index: int
    content: str
    token_estimate: int
    section_hint: str | None = None


def normalize_text(raw: str) -> str:
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def estimate_tokens(text: str) -> int:
    # Rough heuristic (~4 chars/token) — good enough for chunk budgeting.
    return max(1, len(text) // 4) if text else 0


def chunk_text(
    text: str,
    *,
    max_tokens: int = 800,
    overlap_tokens: int = 80,
) -> list[TextChunk]:
    normalized = normalize_text(text)
    if not normalized:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", normalized) if p.strip()]
    chunks: list[TextChunk] = []
    buffer: list[str] = []
    buffer_tokens = 0
    section_hint: str | None = None

    def flush() -> None:
        nonlocal buffer, buffer_tokens, section_hint
        if not buffer:
            return
        content = "\n\n".join(buffer).strip()
        chunks.append(
            TextChunk(
                index=len(chunks),
                content=content,
                token_estimate=estimate_tokens(content),
                section_hint=section_hint,
            )
        )
        if overlap_tokens > 0 and content:
            # Keep a short overlap tail for continuity.
            words = content.split()
            keep = max(1, overlap_tokens // 2)
            tail = " ".join(words[-keep:])
            buffer = [tail]
            buffer_tokens = estimate_tokens(tail)
        else:
            buffer = []
            buffer_tokens = 0

    for para in paragraphs:
        if _looks_like_heading(para):
            section_hint = para[:120]
        tokens = estimate_tokens(para)
        if buffer_tokens + tokens > max_tokens and buffer:
            flush()
        buffer.append(para)
        buffer_tokens += tokens
        if buffer_tokens >= max_tokens:
            flush()

    flush()
    return chunks


def _looks_like_heading(line: str) -> bool:
    if len(line) > 80:
        return False
    if re.match(r"^(chapter\s+\d+|section\s+\d+|\d+\.\s+\S+)", line, re.I):
        return True
    return line == line.title() and " " in line
