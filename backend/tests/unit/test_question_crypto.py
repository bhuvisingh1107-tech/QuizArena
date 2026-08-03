"""Unit tests for AES-GCM question field encryption."""

from app.config import Settings
from app.core.crypto import is_sealed, open_text, seal_text
from app.services.question_crypto import open_option_fields, seal_option_fields


def test_seal_roundtrip_and_legacy_plaintext() -> None:
    key = "unit-test-question-encryption-key"
    sealed = seal_text("What is photosynthesis?", key)
    assert is_sealed(sealed)
    assert open_text(sealed, key) == "What is photosynthesis?"
    assert open_text("legacy plaintext prompt", key) == "legacy plaintext prompt"


def test_option_seal_hides_correct_flag() -> None:
    settings = Settings(question_encryption_key="unit-test-question-encryption-key", app_env="test")
    sealed_text, decoy = seal_option_fields("Paris", True, settings)
    assert decoy is False
    assert is_sealed(sealed_text)
    text, correct = open_option_fields(sealed_text, decoy, settings)
    assert text == "Paris"
    assert correct is True
