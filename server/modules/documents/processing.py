"""Document upload lifecycle and background processing orchestration."""

from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from server.core.config import get_settings
from server.core.database import get_session_factory

from . import persistence
from .access import is_reference_source_type
from .exceptions import (
    ExtractionFailedError,
)
from .ingestion.pipeline import ingest_document
from .journaling import (
    _cleanup_failed_upload,
)
from .metadata import canonicalize_supported_program, detect_metadata
from .schemas import (
    DocumentResponse,
    DocumentUploadResponse,
)
from .slm_processing import prepare_slm_package

logger = logging.getLogger(__name__)

# Restricted source types that only admins can upload
_ADMIN_ONLY_SOURCE_TYPES = {
    "syllabus",
    "curriculum",
    "policy",
    "rubric_sme",
    "rubric_coord",
    "rubric_gad",
    "rubric_itso",
}


def _process_uploaded_document(
    *,
    doc_id: uuid.UUID,
    target_path: Path,
    source_type: str,
    title: str,
    course_title: str | None,
    lesson_title: str | None,
    program: str | None,
    policy_area: str | None,
    uploaded_by: uuid.UUID,
    original_filename: str | None,
    runtime_db: Any | None,
) -> DocumentUploadResponse:
    """Run ingestion after a DB-backed upload intent has been committed."""

    # Reference documents (syllabus) are often scanned CMOs that need
    # multi-minute OCR. Doing that on the request thread times out the upload
    # (surfaces as "Internal Server Error"), so we persist a PROCESSING stub,
    # return immediately, and let a background task (process_document_ingestion)
    # do the heavy extraction + embedding. SLM uploads stay synchronous below.
    if is_reference_source_type(source_type):
        return _persist_reference_stub(
            db=runtime_db,
            doc_id=doc_id,
            target_path=target_path,
            source_type=source_type,
            title=title,
            course_title=course_title,
            lesson_title=lesson_title,
            program=program,
            uploaded_by=uploaded_by,
        )

    error_message: str | None = None

    try:
        chunk_data = ingest_document(str(target_path), source_type, str(doc_id))
        # Enrich policy chunks with their document's policy_area for persistence
        if source_type == "policy" and policy_area:
            for c in chunk_data:
                c.policy_area = policy_area
        page_count = max((chunk.page_number for chunk in chunk_data), default=0)
        has_ocr_pages = any(chunk.is_ocr for chunk in chunk_data)
        if not chunk_data:
            status = "FAILED"
            error_message = "No extractable text was found in the uploaded PDF."
        else:
            status = "PROCESSED"
    except ExtractionFailedError as exc:
        error_message = _sanitize_error(str(exc))
        logger.warning(
            "Document upload processing failed",
            extra={
                "document_id": str(doc_id),
                "file_path": str(target_path),
                "original_filename": original_filename,
                "source_type": source_type,
                "exception_class": exc.__class__.__name__,
                "exception_message": str(exc),
            },
        )
        page_count = 0
        has_ocr_pages = False
        status = "FAILED"
        chunk_data = []
    except Exception as exc:
        error_message = _sanitize_error(
            f"Unexpected preprocessing error: {exc.__class__.__name__}"
        )
        logger.exception(
            "Document upload preprocessing failed with unexpected error",
            extra={
                "document_id": str(doc_id),
                "file_path": str(target_path),
                "original_filename": original_filename,
                "source_type": source_type,
                "exception_class": exc.__class__.__name__,
                "exception_message": str(exc),
            },
        )
        page_count = 0
        has_ocr_pages = False
        status = "FAILED"
        chunk_data = []

    # ── Metadata detection ──────────────────────────────────────────
    detected_metadata: dict[str, str | None] = {}
    if chunk_data:
        try:
            full_text = " ".join(chunk.text for chunk in chunk_data)
            detected_metadata = detect_metadata(full_text, title=title)
        except Exception:
            logger.warning(
                "Metadata detection failed during preprocessing",
                extra={"document_id": str(doc_id)},
                exc_info=True,
            )

    # Merge — never overwrite manually-provided values
    effective_program = canonicalize_supported_program(program)
    if effective_program is None and detected_metadata.get("program"):
        effective_program = detected_metadata["program"]
    effective_lesson_title = lesson_title
    if effective_lesson_title is None and detected_metadata.get("lesson_title"):
        effective_lesson_title = detected_metadata["lesson_title"]
    detected_academic_year = detected_metadata.get("academic_year")
    detected_course_code = detected_metadata.get("course_code")
    # ─────────────────────────────────────────────────────────────────

    if status == "FAILED":
        cleanup_ok = _cleanup_failed_upload(target_path)
        if not cleanup_ok:
            status = "CLEANUP_PENDING"

    uploaded_at = datetime.now(UTC)
    structured_summary = None
    structured_outline = None
    section_summaries = None
    key_facts = None
    processing_warnings = None
    evaluation_readiness = "PENDING"

    if source_type == "slm" and chunk_data:
        package = prepare_slm_package(
            [chunk.model_dump() for chunk in chunk_data],
            title=title,
            course_title=course_title,
            lesson_title=effective_lesson_title,
            program=effective_program,
        )
        structured_summary = package.document_summary
        structured_outline = package.document_outline
        section_summaries = package.section_summaries
        key_facts = package.key_facts
        processing_warnings = package.warnings
        evaluation_readiness = package.readiness_status

    response = DocumentResponse(
        document_id=doc_id,
        title=title,
        course_title=course_title,
        lesson_title=effective_lesson_title,
        source_type=source_type,
        policy_area=policy_area,
        program=effective_program,
        academic_year=detected_academic_year,
        course_code=detected_course_code,
        page_count=page_count,
        processing_status=status,
        has_ocr_pages=has_ocr_pages,
        uploaded_at=uploaded_at,
        uploaded_by=uploaded_by,
        structured_summary=structured_summary,
        structured_outline=structured_outline,
        section_summaries=section_summaries,
        key_facts=key_facts,
        processing_warnings=processing_warnings,
        evaluation_readiness=evaluation_readiness,
    )

    storage_ref = str(target_path)
    if target_path.exists() and status != "FAILED":
        try:
            from server.core.storage import get_storage_backend

            storage = get_storage_backend()
            with target_path.open("rb") as f:
                storage_ref = storage.upload_file(f"{doc_id}.pdf", f)
        except Exception as exc:
            logger.warning("Failed to upload %s to storage backend: %s", doc_id, exc)

    try:
        persistence._persist_document(
            runtime_db,
            response,
            storage_ref,
            uploaded_by,
            commit=False,
        )
        persistence._persist_chunks(runtime_db, doc_id, chunk_data, commit=False)
        if runtime_db is not None:
            runtime_db.commit()
    except Exception:
        if runtime_db is not None:
            runtime_db.rollback()
        raise

    return DocumentUploadResponse(
        document_id=doc_id,
        title=title,
        course_title=course_title,
        lesson_title=effective_lesson_title,
        source_type=source_type,
        policy_area=policy_area,
        processing_status=status,
        academic_year=detected_academic_year,
        course_code=detected_course_code,
        structured_summary=structured_summary,
        evaluation_readiness=evaluation_readiness,
        error_message=error_message,
    )


def _persist_reference_stub(
    *,
    db: Any | None,
    doc_id: uuid.UUID,
    target_path: Path,
    source_type: str,
    title: str,
    course_title: str | None = None,
    lesson_title: str | None = None,
    program: str | None,
    uploaded_by: uuid.UUID,
) -> DocumentUploadResponse:
    """Persist a PROCESSING placeholder row and return immediately.

    Extraction/embedding is deferred to ``process_document_ingestion`` running
    as a background task, so the upload request never blocks on OCR.
    """

    effective_program = canonicalize_supported_program(program)

    uploaded_at = datetime.now(UTC)
    response = DocumentResponse(
        document_id=doc_id,
        title=title,
        course_title=course_title,
        lesson_title=lesson_title,
        source_type=source_type,
        program=effective_program,
        academic_year=None,
        course_code=None,
        page_count=0,
        processing_status="PROCESSING",
        has_ocr_pages=False,
        uploaded_at=uploaded_at,
        uploaded_by=uploaded_by,
        structured_summary=None,
        structured_outline=None,
        section_summaries=None,
        key_facts=None,
        processing_warnings=None,
        evaluation_readiness="PENDING",
    )

    runtime_db = db
    runtime_session = None
    if runtime_db is None and get_settings().database_configured:
        runtime_session = get_session_factory()()
        runtime_db = runtime_session
    storage_ref = str(target_path)
    if target_path.exists():
        try:
            from server.core.storage import get_storage_backend

            storage = get_storage_backend()
            with target_path.open("rb") as f:
                storage_ref = storage.upload_file(f"{doc_id}.pdf", f)
        except Exception as exc:
            logger.warning("Failed to upload %s to storage backend: %s", doc_id, exc)

    try:
        persistence._persist_document(runtime_db, response, storage_ref, uploaded_by)
    finally:
        if runtime_session is not None:
            runtime_session.close()

    return DocumentUploadResponse(
        document_id=doc_id,
        title=title,
        course_title=course_title,
        lesson_title=lesson_title,
        source_type=source_type,
        processing_status="PROCESSING",
        academic_year=None,
        course_code=None,
        structured_summary=None,
        evaluation_readiness="PENDING",
        error_message=None,
    )


def _sanitize_error(raw_message: str) -> str:
    """Strip internal details (file paths, stack traces) from error messages."""
    # Exact mappings first
    if raw_message == "PyMuPDF is not installed":
        return "Document processing is unavailable. Please contact support."
    if raw_message == "Failed to extract document pages":
        return "The PDF could not be read. It may be corrupted or unsupported."
    if raw_message.startswith("File not found:"):
        return "The uploaded file could not be processed."
    if raw_message.startswith("This PDF appears to be scanned"):
        return (
            "This PDF appears to be scanned (image-based) and could not be "
            "read. Ask an administrator to enable OCR, or upload a "
            "text-based PDF."
        )

    # Partial/pattern mappings for OCR errors
    has_unavailable_keywords = (
        "OCR engine is unavailable" in raw_message
        or "missing required language pack" in raw_message
    )
    if has_unavailable_keywords:
        return (
            "Scanned-PDF OCR is unavailable. Please upload a text-based PDF, "
            "or contact an administrator to check OCR/language pack "
            "installation."
        )
    if "OCR execution timed out" in raw_message or "timed out" in raw_message:
        return (
            "OCR page processing timed out. Please upload a smaller "
            "or less complex document."
        )
    if "limit exceeded" in raw_message or "exceeds the maximum" in raw_message:
        return "OCR resource limit exceeded. Please ensure pages do not exceed limits."
    if (
        "OCR execution failed" in raw_message
        or "OCR failed" in raw_message
        or "OCR extraction produced no text" in raw_message
    ):
        return (
            "Scanned PDF page could not be read. Please check the document "
            "quality or upload a text-based PDF."
        )

    # Strip any remaining filesystem paths as a safety net
    sanitized = re.sub(r"[/\\][\w./\\_-]+(?:\.pdf|\.db|\.txt)", "[file]", raw_message)
    # Truncate excessively long messages
    if len(sanitized) > 200:
        sanitized = sanitized[:197] + "..."
    return sanitized
