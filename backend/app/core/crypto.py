"""AES-GCM field encryption for question content at rest.

Ciphertexts are stored as ``qaenc:v1:<base64url(nonce || ciphertext || tag)>``.
Legacy plaintext rows (no prefix) remain readable for backward compatibility.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)

ENC_PREFIX = "qaenc:v1:"
_NONCE_BYTES = 12


class QuestionCryptoError(RuntimeError):
    """Raised when encryption is required but misconfigured or decryption fails."""


def _load_key_material(raw: str) -> bytes:
    """Derive a 32-byte AES key.

    Prefers a urlsafe-base64 or hex 32-byte key. Any other string is accepted as a
    passphrase and hashed with SHA-256 (simple; not HKDF).
    """
    value = raw.strip()
    if not value:
        raise QuestionCryptoError("QUESTION_ENCRYPTION_KEY is empty")
    try:
        decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        if len(decoded) == 32:
            return decoded
    except Exception:
        pass
    try:
        decoded = bytes.fromhex(value)
        if len(decoded) == 32:
            return decoded
    except ValueError:
        pass
    return hashlib.sha256(value.encode("utf-8")).digest()


def is_sealed(value: str | None) -> bool:
    return isinstance(value, str) and value.startswith(ENC_PREFIX)


def seal_text(plaintext: str, key_material: str) -> str:
    """Encrypt UTF-8 plaintext with AES-256-GCM."""
    key = _load_key_material(key_material)
    nonce = os.urandom(_NONCE_BYTES)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    blob = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii").rstrip("=")
    return ENC_PREFIX + blob


def open_text(value: str, key_material: str | None) -> str:
    """Decrypt sealed text, or return plaintext unchanged for legacy rows."""
    if not is_sealed(value):
        return value
    if not key_material or not key_material.strip():
        raise QuestionCryptoError(
            "Encrypted question content requires QUESTION_ENCRYPTION_KEY",
        )
    key = _load_key_material(key_material)
    raw = value[len(ENC_PREFIX) :]
    pad = "=" * (-len(raw) % 4)
    try:
        blob = base64.urlsafe_b64decode(raw + pad)
    except Exception as exc:
        raise QuestionCryptoError("Invalid encrypted question payload") from exc
    if len(blob) <= _NONCE_BYTES:
        raise QuestionCryptoError("Truncated encrypted question payload")
    nonce, ciphertext = blob[:_NONCE_BYTES], blob[_NONCE_BYTES:]
    try:
        plain = AESGCM(key).decrypt(nonce, ciphertext, None)
    except Exception as exc:
        raise QuestionCryptoError("Failed to decrypt question content") from exc
    return plain.decode("utf-8")


def seal_json(payload: dict[str, Any], key_material: str) -> str:
    return seal_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False), key_material)


def open_json(value: str, key_material: str | None) -> dict[str, Any]:
    raw = open_text(value, key_material)
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise QuestionCryptoError("Encrypted payload must be a JSON object")
    return data


def maybe_seal_text(plaintext: str | None, key_material: str | None) -> str | None:
    if plaintext is None:
        return None
    if not key_material or not key_material.strip():
        return plaintext
    if is_sealed(plaintext):
        return plaintext
    return seal_text(plaintext, key_material)


def maybe_open_text(value: str | None, key_material: str | None) -> str | None:
    if value is None:
        return None
    return open_text(value, key_material)
