"""Extractor unit tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.exceptions import ValidationError
from app.services.ai.extractors import extract_text


def test_extract_txt(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("## Arrays\nArrays are contiguous.", encoding="utf-8")
    result = extract_text(path, mime_type="text/plain", filename="notes.txt")
    assert "Arrays" in result.text
    assert result.extractor == "txt"


def test_legacy_ppt_rejected(tmp_path: Path) -> None:
    path = tmp_path / "old.ppt"
    path.write_bytes(b"fake")
    with pytest.raises(ValidationError) as exc:
        extract_text(path, filename="old.ppt")
    assert exc.value.code == "UNSUPPORTED_FILE_TYPE"
    assert "pptx" in exc.value.message.lower()
    assert "pip install" not in exc.value.message.lower()


def test_extract_pdf_when_available(tmp_path: Path) -> None:
    fitz = pytest.importorskip("fitz")
    path = tmp_path / "sample.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Linked Lists chapter")
    doc.save(path)
    doc.close()
    result = extract_text(path, mime_type="application/pdf", filename="sample.pdf")
    assert "Linked Lists" in result.text
    assert result.extractor == "pymupdf"
