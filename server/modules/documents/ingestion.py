"""Layer 1 ingestion: extract, OCR fallback, and chunking."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from .exceptions import ExtractionFailedError, PasswordProtectedPDFError
from .schemas import DocumentChunkData

_MIN_SELECTABLE_TEXT_LEN = 20
_MAX_CHUNK_TOKENS = 2000
_DEFAULT_CHUNK_TOKENS = 450
_DEFAULT_CHUNK_OVERLAP = 60


@dataclass(slots=True)
class ExtractedPage:
    page_number: int
    text: str
    is_ocr: bool


def resolve_agent_domain(source_type: str) -> str:
    domain_map = {
        "rubric_sme": "sme",
        "rubric_coord": "coordinator",
        "rubric_gad": "gad",
        "rubric_itso": "itso",
        "slm": "all",
        "syllabus": "all",
        "curriculum": "all",
    }
    return domain_map.get(source_type, "all")


def ingest_document(
    file_path: str,
    source_type: str,
    document_id: str,
) -> list[DocumentChunkData]:
    """Extract text from a PDF and return Layer-1 chunks."""

    pages = _extract_pages(file_path)
    domain = resolve_agent_domain(source_type)
    doc_uuid = uuid.UUID(document_id)
    chunks: list[DocumentChunkData] = []

    for page in pages:
        page_chunks = _chunk_page_text(page.text)
        for text in page_chunks:
            chunks.append(
                DocumentChunkData(
                    chunk_id=uuid.uuid4(),
                    document_id=doc_uuid,
                    source_type=source_type,
                    agent_domain=domain,
                    page_number=page.page_number,
                    text=text,
                    token_count=_token_count(text),
                    is_ocr=page.is_ocr,
                )
            )

    return chunks


def _extract_pages(file_path: str) -> list[ExtractedPage]:
    pdf = Path(file_path)
    if not pdf.exists():
        raise ExtractionFailedError(f"File not found: {file_path}")

    try:
        import fitz
    except ModuleNotFoundError as exc:
        raise ExtractionFailedError("PyMuPDF is not installed") from exc

    pages: list[ExtractedPage] = []
    try:
        with fitz.open(pdf) as doc:
            if doc.is_encrypted:
                raise PasswordProtectedPDFError("PDF is password-protected")

            for index, page in enumerate(doc, start=1):
                selectable = (page.get_text() or "").strip()
                if len(selectable) >= _MIN_SELECTABLE_TEXT_LEN:
                    pages.append(ExtractedPage(index, selectable, False))
                    continue

                ocr_text = _perform_ocr(page)
                if ocr_text.strip():
                    pages.append(ExtractedPage(index, ocr_text.strip(), True))
                else:
                    pages.append(ExtractedPage(index, "", True))
    except PasswordProtectedPDFError:
        raise
    except Exception as exc:
        raise ExtractionFailedError("Failed to extract document pages") from exc

    return [page for page in pages if page.text.strip()]


def _perform_ocr(page: object) -> str:
    try:
        import pytesseract
    except ModuleNotFoundError:
        return ""

    pixmap = page.get_pixmap(dpi=250)
    try:
        from PIL import Image
    except ModuleNotFoundError:
        return ""

    image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
    try:
        return pytesseract.image_to_string(image)
    except Exception:
        return ""


def _chunk_page_text(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []

    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for sentence in sentences:
        sentence_tokens = _token_count(sentence)
        if sentence_tokens > _MAX_CHUNK_TOKENS:
            chunks.extend(_hard_split(sentence, _DEFAULT_CHUNK_TOKENS))
            continue

        if current_tokens + sentence_tokens > _DEFAULT_CHUNK_TOKENS and current:
            chunk_text = " ".join(current).strip()
            chunks.append(chunk_text)
            overlap = _overlap_tail(chunk_text, _DEFAULT_CHUNK_OVERLAP)
            current = [overlap] if overlap else []
            current_tokens = _token_count(overlap)

        current.append(sentence)
        current_tokens += sentence_tokens

    if current:
        chunks.append(" ".join(current).strip())
    return [chunk for chunk in chunks if chunk]


def _overlap_tail(text: str, overlap_tokens: int) -> str:
    words = text.split()
    if len(words) <= overlap_tokens:
        return text
    return " ".join(words[-overlap_tokens:])


def _hard_split(text: str, max_tokens: int) -> list[str]:
    words = text.split()
    return [
        " ".join(words[index : index + max_tokens])
        for index in range(0, len(words), max_tokens)
    ]


def _token_count(text: str) -> int:
    return len(text.split())


__all__ = ["ingest_document", "resolve_agent_domain"]
