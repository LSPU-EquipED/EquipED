"""Document upload lifecycle and background processing orchestration."""

from __future__ import annotations

import logging
import re
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from server.core.config import get_settings
from server.core.database import get_session_factory
from server.modules.embeddings.service import (
    delete_chroma_vectors_strict,
    embed_and_store_chunks,
)

from . import paths, persistence
from .access import is_reference_source_type
from .exceptions import (
    ExtractionFailedError,
    ForbiddenUploadError,
    UnsupportedFileTypeError,
)
from .ingestion.pipeline import ingest_document
from .journaling import (
    UNVERIFIED_VECTOR_CLEANUP_WARNING,
    _cleanup_failed_upload,
    _create_upload_marker,
    _remove_upload_marker,
)
from .metadata import canonicalize_supported_program, detect_metadata
from .models import VALID_POLICY_AREAS, Document, DocumentChunk
from .schemas import (
    SOURCE_TYPES,
    DocumentResponse,
    DocumentUploadResponse,
)
from .slm import prepare_slm_package
from .slm.tfidf import compute_tfidf_corpus

logger = logging.getLogger(__name__)

_MEM_TFIDF: dict[str, float] = {}

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


def create_document(
    file: UploadFile,
    source_type: str,
    title: str,
    course_title: str | None,
    lesson_title: str | None,
    program: str | None,
    uploaded_by: uuid.UUID,
    user_role: str = "faculty",
    policy_area: str | None = None,
    db: Any | None = None,
) -> DocumentUploadResponse:
    """Persist an upload and run Layer-1 ingestion."""

    canonical_program = _validate_upload(
        file, source_type, program, user_role, policy_area=policy_area
    )
    paths.UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

    doc_id = uuid.uuid4()
    target_path = paths.UPLOAD_ROOT / f"{doc_id}.pdf"

    runtime_db = db
    runtime_session = None
    if runtime_db is None and get_settings().database_configured:
        runtime_session = get_session_factory()()
        runtime_db = runtime_session

    upload_marker: Path | None = None
    try:
        if runtime_db is not None:
            persistence._create_upload_intent(
                runtime_db,
                document_id=doc_id,
                title=title,
                course_title=course_title,
                lesson_title=lesson_title,
                program=canonical_program,
                source_type=source_type,
                policy_area=policy_area,
                file_path=str(target_path),
                uploaded_by=uploaded_by,
            )
        else:
            upload_marker = _create_upload_marker(doc_id, target_path)

        with target_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        response = _process_uploaded_document(
            doc_id=doc_id,
            target_path=target_path,
            source_type=source_type,
            title=title,
            course_title=course_title,
            lesson_title=lesson_title,
            program=canonical_program,
            policy_area=policy_area,
            uploaded_by=uploaded_by,
            original_filename=file.filename,
            runtime_db=runtime_db,
        )
        if (
            upload_marker is not None
            and response.processing_status != "CLEANUP_PENDING"
        ):
            _remove_upload_marker(upload_marker)
        return response
    except Exception:
        if runtime_db is not None:
            runtime_db.rollback()
        cleanup_ok = _cleanup_failed_upload(target_path)
        if runtime_db is not None:
            persistence._mark_interrupted_upload(runtime_db, doc_id, cleanup_ok)
        if upload_marker is not None and cleanup_ok:
            _remove_upload_marker(upload_marker)
        raise
    finally:
        if runtime_session is not None:
            runtime_session.close()


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
            detected_metadata = detect_metadata(full_text)
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

    try:
        persistence._persist_document(
            runtime_db,
            response,
            str(target_path),
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

    _refresh_tfidf_if_needed(source_type)

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
    try:
        persistence._persist_document(
            runtime_db, response, str(target_path), uploaded_by
        )
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
            detected_metadata = detect_metadata(full_text)
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

    _refresh_tfidf_if_needed(source_type)


def _validate_upload(
    file: UploadFile,
    source_type: str,
    program: str | None,
    user_role: str = "faculty",
    policy_area: str | None = None,
) -> str | None:
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise UnsupportedFileTypeError("Only PDF uploads are supported")
    if source_type not in SOURCE_TYPES:
        raise UnsupportedFileTypeError(f"Unsupported source_type: {source_type}")
    canonical_program = canonicalize_supported_program(program)
    # RBAC: only admins can upload institutional knowledge base documents.
    if user_role != "admin" and source_type in _ADMIN_ONLY_SOURCE_TYPES:
        raise ForbiddenUploadError(
            f"Only administrators can upload {source_type} documents. "
            "Faculty members can only upload SLM documents."
        )

    # Curriculum upload requires explicit canonical BSCS or BSInfoTech
    if source_type == "curriculum":
        if not program or not program.strip():
            raise UnsupportedFileTypeError(
                "Curriculum upload requires explicit canonical program "
                "'BSCS' or 'BSInfoTech'."
            )
        if program.strip() not in ("BSCS", "BSInfoTech"):
            if program.strip().upper() == "BSIT":
                raise UnsupportedFileTypeError(
                    "BSIT is a legacy read alias and cannot be used for uploads. "
                    "Use BSInfoTech."
                )
            raise UnsupportedFileTypeError(
                "Curriculum upload requires explicit canonical program "
                "'BSCS' or 'BSInfoTech'."
            )

    if source_type in ("rubric_sme", "rubric_coord", "rubric_gad", "rubric_itso"):
        raise UnsupportedFileTypeError(
            f"Direct PDF upload for {source_type} is not supported. "
            "Use structured rubric tables."
        )
    # Policy documents require a valid policy_area
    if source_type == "policy":
        if not (policy_area and policy_area.strip()):
            raise UnsupportedFileTypeError(
                "policy_area is required for policy documents."
            )
        if policy_area not in VALID_POLICY_AREAS:
            raise UnsupportedFileTypeError(
                f"Invalid policy_area '{policy_area}'. Valid values: "
                f"{', '.join(sorted(VALID_POLICY_AREAS))}."
            )
    # Non-policy documents must not have a policy_area
    if source_type != "policy" and policy_area:
        raise UnsupportedFileTypeError(
            "policy_area is only valid for policy documents."
        )
    if program and program.strip() and canonical_program is None:
        raise UnsupportedFileTypeError(
            "Unsupported program. Only BSCS and BSInfoTech are supported; "
            "BSIT is accepted as an alias."
        )
    return canonical_program


def embed_document_chunks(document_id: uuid.UUID) -> int:
    """Embed a document's chunks and mark them as stored in Chroma."""

    settings = get_settings()
    db = None
    session = None

    if settings.database_configured:
        session = get_session_factory()()
        db = session

    try:
        if db is not None:
            document = db.get(Document, document_id)
            source_type = document.source_type if document is not None else None
        else:
            document = persistence._MEM_DOCUMENTS.get(document_id)
            source_type = document.source_type if document is not None else None

        if source_type == "slm":
            return 0

        chunks = persistence.get_document_chunks(document_id, db=db)
        upserted = embed_and_store_chunks(chunks)
        if db is not None and upserted:
            persistence.mark_chunks_chroma_stored(
                db, [chunk.chunk_id for chunk in chunks]
            )
        elif db is None and upserted:
            for chunk in chunks:
                if isinstance(chunk, dict):
                    chunk["chroma_stored"] = True
        return upserted
    finally:
        if session is not None:
            session.close()


def _refresh_tfidf_if_needed(source_type: str) -> None:
    if source_type != "slm":
        return

    slm_chunks: list[Any] = []
    for document_id, metadata in persistence._MEM_DOCUMENTS.items():
        if metadata.source_type == "slm":
            slm_chunks.extend(persistence._MEM_CHUNKS.get(document_id, []))

    _MEM_TFIDF.clear()
    _MEM_TFIDF.update(compute_tfidf_corpus(slm_chunks))


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


__all__ = [
    "create_document",
    "embed_document_chunks",
    "process_document_ingestion",
]
