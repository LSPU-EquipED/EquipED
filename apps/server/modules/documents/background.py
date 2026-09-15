"""Document upload lifecycle and background processing orchestration."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from server.core.config import get_settings
from server.core.database import get_session_factory
from server.modules.embeddings.service import delete_chroma_vectors_strict

from . import paths, persistence
from .embedding import embed_document_chunks
from .exceptions import (
    ExtractionFailedError,
)
from .ingestion.pipeline import ingest_document
from .journaling import (
    UNVERIFIED_VECTOR_CLEANUP_WARNING,
    _cleanup_failed_upload,
)
from .metadata import canonicalize_supported_program, detect_metadata
from .models import Document, DocumentChunk
from .processing import _sanitize_error
from .schemas import (
    DocumentResponse,
)

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


def _finalize_ingestion_failure(
    session: Any,
    *,
    document_id: uuid.UUID,
    source_type: str,
    file_path: str,
    had_prior_embedded_state: bool,
    warning_message: str | None,
    log_context: str = "failure",
) -> None:
    """Handle terminal ingestion failure with strict vector cleanup and DB state sync.

    Semantics:
    1. If there was prior embedded state, strictly delete Chroma vectors.
    2. If Chroma cleanup fails or cannot be verified:
       - Set processing_status = "FAILED"
       - Set processing_warnings = [unverified_warning]
       - Preserve prior chunks, chroma_stored flag, and file on disk for retry
       - Commit session and return.
    3. If Chroma cleanup succeeds (or was not needed):
       - Set processing_status = "FAILED"
       - Reset chroma_stored = False
       - Set processing_warnings = [warning_message[:200]] (if provided)
       - Delete DocumentChunks in SQL and clear _MEM_CHUNKS
       - Commit session
       - Remove the failed upload file.
    """
    chroma_cleanup_ok = True
    if had_prior_embedded_state:
        try:
            delete_chroma_vectors_strict(str(document_id), source_type)
        except Exception as cleanup_exc:
            logger.exception(
                f"Failed to verify Chroma vector cleanup on {log_context}",
                extra={
                    "document_id": str(document_id),
                    "source_type": source_type,
                    "exception_class": cleanup_exc.__class__.__name__,
                    "exception_message": str(cleanup_exc),
                },
            )
            chroma_cleanup_ok = False

    document = session.get(Document, document_id)
    if document is None:
        return

    document.processing_status = "FAILED"
    if not chroma_cleanup_ok:
        document.processing_warnings = [UNVERIFIED_VECTOR_CLEANUP_WARNING]
        session.commit()
        return

    if hasattr(document, "chroma_stored"):
        document.chroma_stored = False
    document.processing_warnings = [warning_message[:200]] if warning_message else None
    session.query(DocumentChunk).filter(
        DocumentChunk.document_id == document_id
    ).delete(synchronize_session=False)
    persistence._MEM_CHUNKS[document_id] = []
    session.commit()
    _cleanup_failed_upload(Path(file_path))


def process_document_ingestion(document_id: uuid.UUID) -> None:
    """Background worker: OCR-extract, persist chunks, and embed a reference doc.

    Runs off the request thread so multi-minute OCR never times out the upload.
    The DB session is deliberately NOT held across extraction — Neon closes idle
    connections, so we read the file path in a short session, run OCR with no
    session open, then reopen a session for the quick metadata/chunk writes.
    """

    settings = get_settings()
    if not settings.database_configured:
        no_db_warning = (
            "A configured database is required for reference document ingestion."
        )
        mem_doc = persistence._MEM_DOCUMENTS.get(document_id)
        if mem_doc is not None:
            persistence._MEM_DOCUMENTS[document_id] = DocumentResponse(
                document_id=mem_doc.document_id,
                title=mem_doc.title,
                course_title=mem_doc.course_title,
                lesson_title=mem_doc.lesson_title,
                source_type=mem_doc.source_type,
                policy_area=mem_doc.policy_area,
                program=mem_doc.program,
                academic_year=mem_doc.academic_year,
                course_code=mem_doc.course_code,
                page_count=mem_doc.page_count,
                processing_status="FAILED",
                has_ocr_pages=mem_doc.has_ocr_pages,
                uploaded_at=mem_doc.uploaded_at,
                uploaded_by=mem_doc.uploaded_by,
                structured_summary=mem_doc.structured_summary,
                structured_outline=mem_doc.structured_outline,
                section_summaries=mem_doc.section_summaries,
                key_facts=mem_doc.key_facts,
                processing_warnings=[no_db_warning],
                evaluation_readiness="PENDING",
            )
        persistence._MEM_CHUNKS[document_id] = []
        target_path = paths.UPLOAD_ROOT / f"{document_id}.pdf"
        _cleanup_failed_upload(target_path)
        return
    session_factory = get_session_factory()

    # Phase 1 — short-lived read of the file path to OCR.
    session = session_factory()
    try:
        document = session.get(Document, document_id)
        if document is None:
            return
        file_path = document.file_path
        source_type = document.source_type
        program = document.program
        doc_title = document.title
        existing_chunks = (
            session.query(DocumentChunk)
            .filter(DocumentChunk.document_id == document_id)
            .all()
        )
        has_prior_chunks = len(existing_chunks) > 0
        has_prior_chroma = any(
            getattr(c, "chroma_stored", False) for c in existing_chunks
        ) or bool(getattr(document, "chroma_stored", False))
        had_prior_embedded_state = has_prior_chunks or has_prior_chroma
    finally:
        session.close()

    # Phase 2 — heavy OCR/extraction with NO DB session held.
    extraction_error: str | None = None
    try:
        chunk_data = ingest_document(
            file_path, source_type, str(document_id), program=program
        )
    except ExtractionFailedError as exc:
        logger.warning(
            "Background ingestion extraction failed",
            extra={
                "document_id": str(document_id),
                "file_path": file_path,
                "source_type": source_type,
                "exception_class": exc.__class__.__name__,
                "exception_message": str(exc),
            },
        )
        extraction_error = _sanitize_error(str(exc))
        chunk_data = []
    except Exception as exc:
        logger.exception(
            "Background ingestion failed during extraction with unexpected error",
            extra={
                "document_id": str(document_id),
                "file_path": file_path,
                "source_type": source_type,
                "exception_class": exc.__class__.__name__,
                "exception_message": str(exc),
            },
        )
        extraction_error = (
            "The document could not be processed due to an unexpected error."
        )
        chunk_data = []

    if not chunk_data and extraction_error is None:
        extraction_error = "No extractable text was found in the uploaded PDF."

    detected_metadata: dict[str, str | None] = {}
    if chunk_data:
        try:
            full_text = " ".join(chunk.text for chunk in chunk_data)
            detected_metadata = detect_metadata(full_text, title=doc_title)
        except Exception:
            logger.warning(
                "Metadata detection failed during background ingestion",
                extra={"document_id": str(document_id)},
                exc_info=True,
            )

    # Phase 3 — fresh session for the quick writes.
    session = session_factory()
    try:
        if not chunk_data:
            _finalize_ingestion_failure(
                session,
                document_id=document_id,
                source_type=source_type,
                file_path=file_path,
                had_prior_embedded_state=had_prior_embedded_state,
                warning_message=extraction_error,
                log_context="extraction failure",
            )
            return

        persistence._persist_chunks(session, document_id, chunk_data)

        document = session.get(Document, document_id)
        if document is None:
            return
        if not document.program and detected_metadata.get("program"):
            document.program = canonicalize_supported_program(
                detected_metadata["program"]
            )
        if detected_metadata.get("academic_year"):
            document.academic_year = detected_metadata["academic_year"]
        if detected_metadata.get("course_code"):
            document.course_code = detected_metadata["course_code"]
        document.page_count = max(
            (chunk.page_number for chunk in chunk_data), default=0
        )
        document.has_ocr_pages = any(chunk.is_ocr for chunk in chunk_data)
        document.processing_status = "PROCESSED"
        document.processing_warnings = None
        session.commit()
    except Exception:
        session.rollback()
        logger.exception(
            "Background ingestion failed during database write",
            extra={"document_id": str(document_id)},
        )
        generic_error = (
            "The document could not be processed due to an unexpected error."
        )
        try:
            _finalize_ingestion_failure(
                session,
                document_id=document_id,
                source_type=source_type,
                file_path=file_path,
                had_prior_embedded_state=had_prior_embedded_state,
                warning_message=generic_error,
                log_context="database write failure",
            )
        except Exception:
            session.rollback()
            logger.exception(
                "Failed to update document status to FAILED after write error",
                extra={"document_id": str(document_id)},
            )
        return
    finally:
        session.close()

    # Phase 4 — embed into Chroma (opens its own short-lived session internally).
    try:
        embed_document_chunks(document_id)
    except Exception:
        logger.warning(
            "Embedding failed after background ingestion",
            extra={"document_id": str(document_id)},
            exc_info=True,
        )


__all__ = ["process_document_ingestion"]
