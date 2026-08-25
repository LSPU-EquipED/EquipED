"""Layer 1 ingestion: extract, OCR fallback, and chunking."""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from server.core.config import get_settings

from ..exceptions import (
    ExtractionFailedError,
    OcrLimitExceededError,
    PasswordProtectedPDFError,
)
from ..schemas import DocumentChunkData
from .boilerplate import strip_repeated_page_boilerplate
from .chunking import _chunk_page_text, _token_count
from .ocr import perform_ocr_on_page

_MIN_SELECTABLE_TEXT_LEN = 20

logger = logging.getLogger(__name__)


def _has_meaningful_selectable_text(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 100:
        return False
    words = re.findall(r"[a-zA-Z]+", stripped)
    if len(words) < 8:
        return False
    return True


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
        "policy": "all",
    }
    return domain_map.get(source_type, "all")


def ingest_document(
    file_path: str,
    source_type: str,
    document_id: str,
    program: str | None = None,
) -> list[DocumentChunkData]:
    """Extract text from a PDF and return Layer-1 chunks."""

    domain = resolve_agent_domain(source_type)
    doc_uuid = uuid.UUID(document_id)

    pages = _extract_pages(file_path)
    chunks: list[DocumentChunkData] = []

    if source_type == "curriculum":
        from ..curriculum.extraction import filter_curriculum_pages

        filtered_pages = filter_curriculum_pages(pages, program or "")
        for page in filtered_pages:
            page_chunks = _chunk_page_text(page.text)
            for text in page_chunks:
                chunks.append(
                    DocumentChunkData(
                        chunk_id=uuid.uuid4(),
                        document_id=doc_uuid,
                        source_type="curriculum",
                        agent_domain=domain,
                        page_number=page.page_number,
                        text=text,
                        token_count=_token_count(text),
                        is_ocr=page.is_ocr,
                        chunk_index=len(chunks),
                    )
                )
        return chunks

    if source_type == "syllabus":
        return _ingest_syllabus_course_contents(file_path, pages, domain, doc_uuid)

    if source_type == "policy":
        from ..policy.chunking import build_policy_chunks

        return build_policy_chunks(pages, domain, doc_uuid)

    for page in pages:
        if not page.text.strip():
            continue
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


def prepare_canonical_source(file_path: str) -> str:
    """Return the cleaned, immutable source text for one evaluation.

    This deliberately uses the same page extraction path as ingestion.  It is
    an in-memory preparation step only: no chunks, document state, or
    embeddings are created as a side effect.

    ``file_path`` is supplied by the owning document/evaluation service; that
    caller remains responsible for ownership and upload-root/path validation.
    """
    pages = _extract_pages(file_path)
    source = "\n\n".join(page.text.strip() for page in pages if page.text.strip())
    if not source:
        raise ExtractionFailedError("No extractable text was found in the PDF")
    return source


def _ingest_syllabus_course_contents(
    file_path: str,
    pages: list[ExtractedPage],
    domain: str,
    doc_uuid: uuid.UUID,
) -> list[DocumentChunkData]:
    from ..syllabus.extraction import extract_syllabus_course_contents

    chunks: list[DocumentChunkData] = []
    records = extract_syllabus_course_contents(file_path, pages)
    for record in records:
        for part_index, text in enumerate(_chunk_page_text(record.content)):
            chunks.append(
                DocumentChunkData(
                    chunk_id=uuid.uuid4(),
                    document_id=doc_uuid,
                    source_type="syllabus",
                    agent_domain=domain,
                    page_number=record.page_number,
                    text=text,
                    token_count=_token_count(text),
                    is_ocr=record.is_ocr,
                    section_ref=(
                        f"syllabus_course_content:{record.row_index + 1}"
                        f":{part_index + 1}"
                    ),
                    chunk_index=len(chunks),
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

            raw_pages: list[str] = []
            is_ocr_flags: list[bool] = []
            page_numbers: list[int] = []
            settings = get_settings()

            # Pre-scan pages to count how many require OCR
            ocr_candidate_indices = []
            for index, page in enumerate(doc, start=1):
                selectable = (page.get_text() or "").strip()
                if not _has_meaningful_selectable_text(selectable):
                    ocr_candidate_indices.append(index)

            if len(ocr_candidate_indices) > settings.ocr_max_pages:
                raise OcrLimitExceededError(
                    f"Document requires OCR for {len(ocr_candidate_indices)} "
                    f"pages, which exceeds the maximum limit of "
                    f"{settings.ocr_max_pages} pages."
                )

            for index, page in enumerate(doc, start=1):
                selectable = (page.get_text() or "").strip()
                if _has_meaningful_selectable_text(selectable):
                    raw_pages.append(selectable)
                    is_ocr_flags.append(False)
                    page_numbers.append(index)
                    continue

                # Run OCR using our new robust implementation
                outcome = perform_ocr_on_page(page, settings)
                if outcome.is_blank:
                    logger.info(
                        "Skipping visually blank page during OCR extraction",
                        extra={"page_number": index, "file_path": str(pdf)},
                    )
                    continue

                if not outcome.text.strip():
                    raise ExtractionFailedError(
                        f"OCR extraction produced no text for page {index}"
                    )

                raw_pages.append(outcome.text)
                is_ocr_flags.append(True)
                page_numbers.append(index)
    except (ExtractionFailedError, PasswordProtectedPDFError):
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

    cleaned_pages = strip_repeated_page_boilerplate(raw_pages)
    pages = [
        ExtractedPage(page_number, text, is_ocr)
        for page_number, text, is_ocr in zip(
            page_numbers, cleaned_pages, is_ocr_flags, strict=False
        )
    ]

    return pages


__all__ = ["ingest_document", "prepare_canonical_source", "resolve_agent_domain"]
