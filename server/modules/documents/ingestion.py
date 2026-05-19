"""Layer 1 ingestion: extract, OCR fallback, and chunking."""

from __future__ import annotations

import logging
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
_MIN_MERGE_THRESHOLD = 100

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ExtractedPage:
    page_number: int
    text: str
    is_ocr: bool


@dataclass(slots=True)
class _ChunkDraft:
    text: str
    units: list[str]
    token_count: int


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
        logger.exception(
            "Document extraction failed",
            extra={
                "file_path": str(pdf),
                "exception_class": exc.__class__.__name__,
                "exception_message": str(exc),
            },
        )
        raise ExtractionFailedError("Failed to extract document pages") from exc

    return [page for page in pages if page.text.strip()]


def _perform_ocr(page: object) -> str:
    try:
        import pytesseract
    except ModuleNotFoundError:
        return ""

    pixmap = page.get_pixmap(dpi=250)  # type: ignore[attr-defined]
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
    normalized = re.sub(r"\r\n?", "\n", text).strip()
    if not normalized:
        return []

    structural_units = _split_structural_units(normalized)
    if len(structural_units) == 1 and _looks_weak_structure(normalized):
        structural_units = _split_sentence_units(normalized)

    drafts = _assemble_chunks(structural_units)
    drafts = _merge_tiny_chunks(drafts)
    return [draft.text for draft in drafts]


def _split_structural_units(text: str) -> list[str]:
    blocks = [block.strip() for block in re.split(r"\n\s*\n+", text) if block.strip()]
    if not blocks:
        return []

    units: list[str] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        if len(lines) == 1:
            units.append(lines[0])
        else:
            units.append("\n".join(lines))
    return units


def _looks_weak_structure(text: str) -> bool:
    return len([block for block in re.split(r"\n\s*\n+", text) if block.strip()]) <= 1


def _split_sentence_units(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", normalized)
        if sentence.strip()
    ]
    if not sentences:
        return []

    units: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for sentence in sentences:
        sentence_tokens = _token_count(sentence)
        if sentence_tokens > _MAX_CHUNK_TOKENS:
            if current:
                units.append(" ".join(current).strip())
                current = []
                current_tokens = 0
            units.extend(_hard_split(sentence, _DEFAULT_CHUNK_TOKENS))
            continue

        if current and current_tokens + sentence_tokens > _DEFAULT_CHUNK_TOKENS:
            units.append(" ".join(current).strip())
            current = []
            current_tokens = 0

        current.append(sentence)
        current_tokens += sentence_tokens

    if current:
        units.append(" ".join(current).strip())
    return [unit for unit in units if unit]


def _assemble_chunks(units: list[str]) -> list[_ChunkDraft]:
    drafts: list[_ChunkDraft] = []
    current_units: list[str] = []
    current_tokens = 0
    pending_overlap = ""
    pending_overlap_tokens = 0

    for unit in units:
        unit = unit.strip()
        if not unit:
            continue

        unit_tokens = _token_count(unit)
        if unit_tokens > _MAX_CHUNK_TOKENS:
            if current_units:
                drafts.append(_draft_from_units(current_units))
                current_units = []
                current_tokens = 0
            pending_overlap = ""
            pending_overlap_tokens = 0
            drafts.extend(_drafts_from_hard_split(unit))
            continue

        if not current_units and pending_overlap:
            if pending_overlap_tokens + unit_tokens <= _DEFAULT_CHUNK_TOKENS:
                current_units = [pending_overlap]
                current_tokens = pending_overlap_tokens
            pending_overlap = ""
            pending_overlap_tokens = 0

        if current_units and current_tokens + unit_tokens > _DEFAULT_CHUNK_TOKENS:
            drafts.append(_draft_from_units(current_units))
            pending_overlap = _build_overlap_seed(current_units)
            pending_overlap_tokens = _token_count(pending_overlap)
            current_units = []
            current_tokens = 0

            if (
                pending_overlap
                and pending_overlap_tokens + unit_tokens <= _DEFAULT_CHUNK_TOKENS
            ):
                current_units = [pending_overlap]
                current_tokens = pending_overlap_tokens
                pending_overlap = ""
                pending_overlap_tokens = 0

        current_units.append(unit)
        current_tokens += unit_tokens

    if current_units:
        drafts.append(_draft_from_units(current_units))

    return [draft for draft in drafts if draft.text]


def _merge_tiny_chunks(drafts: list[_ChunkDraft]) -> list[_ChunkDraft]:
    merged: list[_ChunkDraft] = []
    for draft in drafts:
        if merged and draft.token_count < _MIN_MERGE_THRESHOLD:
            previous = merged[-1]
            combined_text = f"{previous.text}\n\n{draft.text}".strip()
            combined_tokens = _token_count(combined_text)
            if combined_tokens <= _MAX_CHUNK_TOKENS:
                merged[-1] = _ChunkDraft(
                    text=combined_text,
                    units=previous.units + draft.units,
                    token_count=combined_tokens,
                )
                continue
        merged.append(draft)
    return merged


def _draft_from_units(units: list[str]) -> _ChunkDraft:
    text = "\n\n".join(unit.strip() for unit in units if unit.strip()).strip()
    return _ChunkDraft(
        text=text,
        units=[unit for unit in units if unit.strip()],
        token_count=_token_count(text),
    )


def _drafts_from_hard_split(text: str) -> list[_ChunkDraft]:
    parts = _hard_split(text, _DEFAULT_CHUNK_TOKENS, _DEFAULT_CHUNK_OVERLAP)
    return [
        _ChunkDraft(text=part, units=[part], token_count=_token_count(part))
        for part in parts
        if part
    ]


def _build_overlap_seed(units: list[str]) -> str:
    if not units:
        return ""

    last_unit = units[-1].strip()
    if not last_unit:
        return ""

    if _token_count(last_unit) <= _DEFAULT_CHUNK_OVERLAP:
        return last_unit

    sentence_tail = _sentence_tail(last_unit)
    if sentence_tail and _token_count(sentence_tail) <= _DEFAULT_CHUNK_OVERLAP:
        return sentence_tail

    return _word_tail(last_unit, _DEFAULT_CHUNK_OVERLAP)


def _sentence_tail(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", normalized)
        if sentence.strip()
    ]
    if not sentences:
        return ""
    return sentences[-1]


def _word_tail(text: str, overlap_tokens: int) -> str:
    words = text.split()
    if not words:
        return ""
    if len(words) <= overlap_tokens:
        return text.strip()
    return " ".join(words[-overlap_tokens:])


def _hard_split(text: str, max_tokens: int, overlap_tokens: int = 0) -> list[str]:
    words = text.split()
    if not words:
        return []

    step = max(1, max_tokens - overlap_tokens)
    chunks: list[str] = []
    for index in range(0, len(words), step):
        chunk = " ".join(words[index : index + max_tokens]).strip()
        if chunk:
            chunks.append(chunk)
        if index + max_tokens >= len(words):
            break
    return chunks


def _token_count(text: str) -> int:
    return len(text.split())


def _has_weak_structure(text: str) -> bool:
    return _looks_weak_structure(text)


__all__ = ["ingest_document", "resolve_agent_domain"]
