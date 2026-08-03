"""Document text extraction for AI quiz generation (optional heavy deps)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".ppt",
    ".pptx",
    ".doc",
    ".docx",
    ".png",
    ".jpg",
    ".jpeg",
    ".mp4",
    ".txt",
}

ALLOWED_MIME_PREFIXES = (
    "application/pdf",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml",
    "image/png",
    "image/jpeg",
    "video/mp4",
    "text/plain",
)


@dataclass
class ExtractionResult:
    text: str
    extractor: str


def extract_text(path: Path, *, mime_type: str = "", filename: str = "") -> ExtractionResult:
    suffix = path.suffix.lower() or Path(filename).suffix.lower()
    if suffix == ".txt" or mime_type.startswith("text/plain"):
        return ExtractionResult(text=path.read_text(encoding="utf-8", errors="ignore"), extractor="txt")
    if suffix == ".pdf" or mime_type == "application/pdf":
        return _extract_pdf(path)
    if suffix in {".pptx", ".ppt"} or "presentation" in mime_type:
        return _extract_pptx(path)
    if suffix in {".docx", ".doc"} or "wordprocessingml" in mime_type or mime_type == "application/msword":
        return _extract_docx(path)
    if suffix in {".png", ".jpg", ".jpeg"} or mime_type.startswith("image/"):
        return _extract_image_ocr(path)
    if suffix == ".mp4" or mime_type.startswith("video/"):
        return _extract_video_whisper(path)
    raise ValueError(f"Unsupported source type: {suffix or mime_type}")


def _extract_pdf(path: Path) -> ExtractionResult:
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise RuntimeError(
            "PDF extraction requires PyMuPDF. Install with: pip install pymupdf"
        ) from exc
    doc = fitz.open(path)
    parts: list[str] = []
    try:
        for page in doc:
            parts.append(page.get_text("text"))
    finally:
        doc.close()
    return ExtractionResult(text="\n".join(parts).strip(), extractor="pymupdf")


def _extract_pptx(path: Path) -> ExtractionResult:
    try:
        from pptx import Presentation
    except ImportError as exc:
        raise RuntimeError(
            "PPTX extraction requires python-pptx. Install with: pip install python-pptx"
        ) from exc
    prs = Presentation(str(path))
    parts: list[str] = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text:
                parts.append(shape.text)
    return ExtractionResult(text="\n".join(parts).strip(), extractor="python-pptx")


def _extract_docx(path: Path) -> ExtractionResult:
    try:
        import docx
    except ImportError as exc:
        raise RuntimeError(
            "DOCX extraction requires python-docx. Install with: pip install python-docx"
        ) from exc
    document = docx.Document(str(path))
    parts = [p.text for p in document.paragraphs if p.text.strip()]
    return ExtractionResult(text="\n".join(parts).strip(), extractor="python-docx")


def _extract_image_ocr(path: Path) -> ExtractionResult:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "Image OCR requires pillow + pytesseract. Install with: "
            "pip install pillow pytesseract (and system tesseract)"
        ) from exc
    text = pytesseract.image_to_string(Image.open(path))
    return ExtractionResult(text=text.strip(), extractor="tesseract")


def _extract_video_whisper(path: Path) -> ExtractionResult:
    try:
        import whisper
    except ImportError as exc:
        raise RuntimeError(
            "Video transcription requires openai-whisper. Install with: pip install openai-whisper"
        ) from exc
    model = whisper.load_model("base")
    result = model.transcribe(str(path))
    text = str(result.get("text") or "").strip()
    return ExtractionResult(text=text, extractor="whisper")
