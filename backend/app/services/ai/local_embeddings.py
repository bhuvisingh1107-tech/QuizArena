"""Deterministic local embeddings when a provider has no /embeddings API."""

from __future__ import annotations

import hashlib
import math


def hash_embeddings(texts: list[str], *, dims: int = 64) -> list[list[float]]:
    """Build stable unit-ish vectors from text hashes (not semantic; storage only)."""
    vectors: list[list[float]] = []
    for text in texts:
        seed = hashlib.sha256(text.encode("utf-8", errors="replace")).digest()
        values: list[float] = []
        while len(values) < dims:
            seed = hashlib.sha256(seed).digest()
            values.extend((byte / 127.5) - 1.0 for byte in seed)
        clipped = values[:dims]
        norm = math.sqrt(sum(v * v for v in clipped)) or 1.0
        vectors.append([v / norm for v in clipped])
    return vectors
