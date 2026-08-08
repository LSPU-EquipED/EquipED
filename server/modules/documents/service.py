"""Documents service orchestration for upload and retrieval."""

from __future__ import annotations

import logging
import os
import re
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from server.core.config import get_settings
from server.core.database import get_session_factory
from server.modules.embeddings.service import embed_and_store_chunks

from .exceptions import (
    DocumentNotFoundError,
    ExtractionFailedError,
    ForbiddenUploadError,
    ReferenceDeleteConflictError,
    ReferenceDeleteInvalidTypeError,
    ReferenceRebuildError,
    UnsupportedFileTypeError,
)
from .ingestion import ingest_document
from .metadata import canonicalize_supported_program, detect_metadata
from .models import VALID_POLICY_AREAS, Document, DocumentChunk
from .policy_service import (  # noqa: F401  — re-exported for router
    delete_policy_document,
    get_healthy_policy_allowlist,
    is_retrieval_ready_policy_document,
    is_source_healthy_policy_document,
    list_policy_documents,
    rebuild_policy_embeddings,
    validate_policy_chunks,
)
from .preprocessing import prepare_slm_package
from .schemas import (
    POLICY_SOURCE_TYPES,
    REFERENCE_SOURCE_TYPES,
    SOURCE_TYPES,
    CurriculumSuggestionItem,
    CurriculumSuggestionResponse,
    DocumentChunkResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadResponse,
    ReferenceDeleteResponse,
    ReferenceLibraryItem,
    ReferenceLibraryResponse,
    ReferenceRebuildResponse,
)
from .tfidf import compute_tfidf_corpus

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
UPLOAD_ROOT = _PROJECT_ROOT / "uploads"
UPLOAD_JOURNAL_ROOT = UPLOAD_ROOT / ".upload-journal"
logger = logging.getLogger(__name__)

_MEM_DOCUMENTS: dict[uuid.UUID, DocumentResponse] = {}
_MEM_DOCUMENT_OWNERS: dict[uuid.UUID, uuid.UUID] = {}
_MEM_CHUNKS: dict[uuid.UUID, list[Any]] = {}
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


def is_reference_source_type(source_type: str) -> bool:
    """Return True if the source type is a shared reference (syllabus or curriculum)."""
    return source_type in REFERENCE_SOURCE_TYPES


def is_policy_source_type(source_type: str) -> bool:
    """Return True if the source type is a policy document."""
    return source_type in POLICY_SOURCE_TYPES


def _is_document_accessible(
    document,
    current_user_id: uuid.UUID,
    current_user_role: str | None = None,
) -> bool:
    """Check whether a user may read/access a document row.

    Reference documents (syllabus, curriculum) are shared to all
    authenticated users. Policy documents are admin-only — faculty
    requests are denied without existence leakage. SLMs and other
    types remain owner-only.
    """
    if is_reference_source_type(document.source_type):
        return True
    if is_policy_source_type(document.source_type):
        return current_user_role == "admin"
    if current_user_id is not None:
        return document.uploaded_by == current_user_id
    return False


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
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

    doc_id = uuid.uuid4()
    target_path = UPLOAD_ROOT / f"{doc_id}.pdf"

    runtime_db = db
    runtime_session = None
    if runtime_db is None and get_settings().database_configured:
        runtime_session = get_session_factory()()
        runtime_db = runtime_session

    upload_marker: Path | None = None
    try:
        if runtime_db is not None:
            _create_upload_intent(
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
            _mark_interrupted_upload(runtime_db, doc_id, cleanup_ok)
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

    # Reference documents (syllabus/curriculum) are often scanned CMOs that need
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
        _persist_document(
            runtime_db,
            response,
            str(target_path),
            uploaded_by,
            commit=False,
        )
        _persist_chunks(runtime_db, doc_id, chunk_data, commit=False)
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
        course_title=None,
        lesson_title=None,
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
        _persist_document(runtime_db, response, str(target_path), uploaded_by)
    finally:
        if runtime_session is not None:
            runtime_session.close()

    return DocumentUploadResponse(
        document_id=doc_id,
        title=title,
        course_title=None,
        lesson_title=None,
        source_type=source_type,
        processing_status="PROCESSING",
        academic_year=None,
        course_code=None,
        structured_summary=None,
        evaluation_readiness="PENDING",
        error_message=None,
    )


def process_document_ingestion(document_id: uuid.UUID) -> None:
    """Background worker: OCR-extract, persist chunks, and embed a reference doc.

    Runs off the request thread so multi-minute OCR never times out the upload.
    The DB session is deliberately NOT held across extraction — Neon closes idle
    connections, so we read the file path in a short session, run OCR with no
    session open, then reopen a session for the quick metadata/chunk writes.
    """

    settings = get_settings()
    if not settings.database_configured:
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
    finally:
        session.close()

    # Phase 2 — heavy OCR/extraction with NO DB session held.
    try:
        chunk_data = ingest_document(
            file_path, source_type, str(document_id), program=program
        )
    except ExtractionFailedError:
        chunk_data = []
    except Exception:
        logger.exception(
            "Background ingestion failed during extraction",
            extra={"document_id": str(document_id)},
        )
        chunk_data = []

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
        document = session.get(Document, document_id)
        if document is None:
            return
        if not chunk_data:
            document.processing_status = "FAILED"
            session.commit()
            _cleanup_failed_upload(Path(file_path))
            return

        _persist_chunks(session, document_id, chunk_data)

        document = session.get(Document, document_id)
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
        session.commit()
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


def get_document(
    document_id: uuid.UUID,
    current_user_id: uuid.UUID,
    current_user_role: str,
    db: Any | None = None,
) -> DocumentResponse:
    if db is not None:
        row = db.get(Document, document_id)
        if row is not None:
            if not _is_document_accessible(row, current_user_id, current_user_role):
                raise DocumentNotFoundError(f"Document {document_id} not found")
            return DocumentResponse(
                document_id=row.document_id,
                title=row.title,
                course_title=row.course_title,
                lesson_title=row.lesson_title,
                source_type=row.source_type,
                policy_area=row.policy_area,
                program=row.program,
                academic_year=row.academic_year,
                course_code=row.course_code,
                page_count=row.page_count,
                processing_status=row.processing_status,
                has_ocr_pages=row.has_ocr_pages,
                uploaded_at=row.uploaded_at,
                uploaded_by=row.uploaded_by,
                structured_summary=row.structured_summary,
                structured_outline=row.structured_outline,
                section_summaries=row.section_summaries,
                key_facts=row.key_facts,
                processing_warnings=row.processing_warnings,
                evaluation_readiness=row.evaluation_readiness,
                chunks=_chunk_responses(get_document_chunks(document_id, db=db)),
            )

    fallback = _MEM_DOCUMENTS.get(document_id)
    if fallback is None:
        raise DocumentNotFoundError(f"Document {document_id} not found")
    if is_policy_source_type(fallback.source_type):
        if current_user_role != "admin":
            raise DocumentNotFoundError(f"Document {document_id} not found")
    elif is_reference_source_type(fallback.source_type):
        pass  # shared to all
    else:
        owner_id = _MEM_DOCUMENT_OWNERS.get(document_id)
        if owner_id != current_user_id:
            raise DocumentNotFoundError(f"Document {document_id} not found")
    return fallback.model_copy(
        update={"chunks": _chunk_responses(get_document_chunks(document_id, db=None))}
    )


def get_syllabus_course_contents(
    document_id: uuid.UUID,
    current_user_id: uuid.UUID,
    current_user_role: str,
    db: Any | None = None,
):
    """Return authoritative persisted Course Contents chunks for a syllabus."""
    from .schemas import SyllabusCourseContentItem, SyllabusCourseContentsResponse

    document = get_document(
        document_id, current_user_id, current_user_role, db=db
    )
    if document.source_type != "syllabus":
        raise ValueError("Course contents are only available for syllabus documents.")
    chunks = sorted(
        (
            chunk
            for chunk in get_document_chunks(document_id, db=db)
            if (getattr(chunk, "section_ref", None) or "").startswith(
                "syllabus_course_content:"
            )
        ),
        key=lambda chunk: (
            getattr(chunk, "chunk_index", None)
            if getattr(chunk, "chunk_index", None) is not None
            else 10**9,
            getattr(chunk, "page_number", 0),
        ),
    )
    return SyllabusCourseContentsResponse(
        document_id=document_id,
        document_title=document.title,
        contents=[
            SyllabusCourseContentItem(
                content_ref=str(chunk.section_ref).split(":", 1)[1],
                content_text=str(chunk.text),
                page_number=int(chunk.page_number),
                extraction_method="ocr" if bool(chunk.is_ocr) else "embedded_text",
                chunk_id=chunk.chunk_id,
                row_index=int(chunk.chunk_index or 0),
            )
            for chunk in chunks
        ],
    )


def list_documents(
    source_type: str | None,
    program: str | None,
    page: int,
    page_size: int,
    current_user_id: uuid.UUID,
    current_user_role: str,
    db: Any | None = None,
) -> DocumentListResponse:
    items: list[DocumentResponse]
    if db is not None:
        query = db.query(Document)
        from sqlalchemy import or_

        query = query.filter(
            or_(
                Document.uploaded_by == current_user_id,
                Document.source_type.in_(REFERENCE_SOURCE_TYPES),
            )
        )
        # Policy documents are admin-only — never exposed to faculty via list
        if current_user_role != "admin":
            query = query.filter(
                Document.source_type.notin_(POLICY_SOURCE_TYPES)
            )
        if source_type:
            query = query.filter(Document.source_type == source_type)
        if program:
            canonical_program = canonicalize_supported_program(program)
            if canonical_program is None:
                raise ValueError(
                    "Unsupported program filter. Only BSCS and BSInfoTech "
                    "are supported; "
                    "BSIT is accepted as an alias."
                )
            from sqlalchemy import func

            values = [canonical_program]
            if canonical_program == "BSInfoTech":
                values.append("BSIT")
            query = query.filter(
                func.lower(Document.program).in_([value.lower() for value in values])
            )
        total = query.count()
        rows = (
            query.order_by(Document.uploaded_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        items = [
            DocumentResponse(
                document_id=row.document_id,
                title=row.title,
                course_title=row.course_title,
                lesson_title=row.lesson_title,
                source_type=row.source_type,
                policy_area=row.policy_area,
                program=row.program,
                academic_year=row.academic_year,
                course_code=row.course_code,
                page_count=row.page_count,
                processing_status=row.processing_status,
                has_ocr_pages=row.has_ocr_pages,
                uploaded_at=row.uploaded_at,
                uploaded_by=row.uploaded_by,
                structured_summary=row.structured_summary,
                structured_outline=row.structured_outline,
                section_summaries=row.section_summaries,
                key_facts=row.key_facts,
                processing_warnings=row.processing_warnings,
                evaluation_readiness=row.evaluation_readiness,
            )
            for row in rows
        ]
        return DocumentListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    mem_items = list(_MEM_DOCUMENTS.values())
    mem_items = [
        item
        for item in mem_items
        if (
            _MEM_DOCUMENT_OWNERS.get(item.document_id) == current_user_id
            or is_reference_source_type(item.source_type)
            or (
                is_policy_source_type(item.source_type)
                and current_user_role == "admin"
            )
        )
    ]
    if source_type:
        mem_items = [item for item in mem_items if item.source_type == source_type]
    if program:
        canonical_program = canonicalize_supported_program(program)
        if canonical_program is None:
            raise ValueError(
                "Unsupported program filter. Only BSCS and BSInfoTech "
                "are supported; "
                "BSIT is accepted as an alias."
            )
        accepted = {canonical_program.lower()}
        if canonical_program == "BSInfoTech":
            accepted.add("bsit")
        mem_items = [
            item for item in mem_items if (item.program or "").lower() in accepted
        ]
    total = len(mem_items)
    start = (page - 1) * page_size
    end = start + page_size
    return DocumentListResponse(
        items=mem_items[start:end],
        total=total,
        page=page,
        page_size=page_size,
    )


def list_reference_documents(
    db: Any | None = None,
) -> ReferenceLibraryResponse:
    """Admin-only listing of syllabus/curriculum documents with computed health."""
    if db is None:
        return ReferenceLibraryResponse(items=[], total=0)

    from server.modules.embeddings.service import check_chroma_availability

    rows = (
        db.query(Document)
        .filter(Document.source_type.in_(REFERENCE_SOURCE_TYPES))
        .order_by(Document.uploaded_at.desc())
        .all()
    )

    items: list[ReferenceLibraryItem] = []
    for row in rows:
        chunk_count = (
            db.query(DocumentChunk)
            .filter(DocumentChunk.document_id == row.document_id)
            .count()
        )
        file_exists = Path(row.file_path).exists() if row.file_path else False
        chroma_available = check_chroma_availability(
            str(row.document_id), row.source_type
        )
        embedding_ready = (
            row.processing_status == "PROCESSED"
            and chunk_count > 0
            and chroma_available
        )
        items.append(
            ReferenceLibraryItem(
                document_id=row.document_id,
                title=row.title,
                source_type=row.source_type,
                program=row.program,
                course_code=row.course_code,
                academic_year=row.academic_year,
                course_title=row.course_title,
                lesson_title=row.lesson_title,
                page_count=row.page_count,
                uploaded_at=row.uploaded_at,
                uploaded_by=row.uploaded_by,
                processing_status=row.processing_status,
                file_exists=file_exists,
                chunk_count=chunk_count,
                chroma_available=chroma_available,
                embedding_ready=embedding_ready,
            )
        )

    return ReferenceLibraryResponse(items=items, total=len(items))


def is_syllabus_reference_ready(document: Document, db: Any) -> tuple[bool, int]:
    """Check authoritative Course Contents and the local retrieval index."""
    if document.source_type != "syllabus" or document.processing_status != "PROCESSED":
        return False, 0
    from server.modules.auth.models import User, UserRole

    uploaded_by_admin = (
        db.query(User)
        .filter(
            User.user_id == document.uploaded_by,
            User.role == UserRole.ADMIN,
        )
        .count()
        > 0
    )
    if not uploaded_by_admin:
        return False, 0
    content_count = (
        db.query(DocumentChunk)
        .filter(
            DocumentChunk.document_id == document.document_id,
            DocumentChunk.section_ref.like("syllabus_course_content:%"),
        )
        .count()
    )
    if content_count == 0:
        return False, 0
    from server.modules.embeddings.service import check_chroma_availability

    return (
        check_chroma_availability(str(document.document_id), "syllabus"),
        content_count,
    )


def list_available_syllabus_references(db: Any):
    """Return shared syllabi that can be used by the alignment retrieval path."""
    from server.modules.documents.schemas import (
        SyllabusReferenceOption,
        SyllabusReferenceOptionsResponse,
    )

    rows = (
        db.query(Document)
        .filter(
            Document.source_type == "syllabus",
            Document.processing_status == "PROCESSED",
        )
        .order_by(Document.uploaded_at.desc())
        .all()
    )
    items = []
    for row in rows:
        ready, content_count = is_syllabus_reference_ready(row, db)
        if not ready:
            continue
        items.append(
            SyllabusReferenceOption(
                document_id=row.document_id,
                title=row.title,
                program=row.program,
                course_code=row.course_code,
                academic_year=row.academic_year,
                content_count=content_count,
            )
        )
    return SyllabusReferenceOptionsResponse(items=items, total=len(items))


def stream_document_file(
    document_id: uuid.UUID,
    current_user_id: uuid.UUID,
    current_user_role: str | None = None,
    db: Any | None = None,
) -> Path:
    """Return the local file path for a document, enforcing access rules.

    Reference documents are shared to authenticated users.
    Policy documents are admin-only.
    SLMs remain owner-only.
    Raises DocumentNotFoundError if the document is not found, not
    accessible, or the local file is missing.
    """
    if db is None:
        raise DocumentNotFoundError(f"Document {document_id} not found")

    row = db.get(Document, document_id)
    if row is None:
        raise DocumentNotFoundError(f"Document {document_id} not found")

    if not _is_document_accessible(row, current_user_id, current_user_role):
        raise DocumentNotFoundError(f"Document {document_id} not found")

    file_path = Path(row.file_path) if row.file_path else None
    if file_path is None or not file_path.exists():
        raise DocumentNotFoundError(f"Document file {document_id} not found")

    return file_path


def delete_reference_document(
    document_id: uuid.UUID,
    db: Any | None = None,
) -> ReferenceDeleteResponse:
    """Admin-only delete of a reference document with best-effort cleanup.

    1. Check for referencing EvaluationJob rows → 409 Conflict
    2. Delete Chroma vectors (tolerate missing)
    3. Delete DocumentChunk rows
    4. Delete the Document row
    5. Delete the local PDF file (tolerate missing)
    """
    if db is None:
        raise DocumentNotFoundError(f"Document {document_id} not found")

    from server.modules.embeddings.service import delete_chroma_vectors
    from server.modules.evaluations.models import EvaluationJob

    row = db.get(Document, document_id)
    if row is None:
        raise DocumentNotFoundError(f"Document {document_id} not found")

    details: dict[str, object] = {}

    # Step 0: Validate source type — only reference documents can be deleted here
    if not is_reference_source_type(row.source_type):
        err_msg = (
            f"Document {document_id} has source_type='{row.source_type}'; "
            "only syllabus and curriculum documents can be deleted "
            "through this endpoint."
        )
        raise ReferenceDeleteInvalidTypeError(err_msg)

    # Step 1: Check for evaluation job references
    ref_count = (
        db.query(EvaluationJob)
        .filter(
            (EvaluationJob.syllabus_id == document_id)
            | (EvaluationJob.curriculum_id == document_id)
        )
        .count()
    )
    if ref_count > 0:
        raise ReferenceDeleteConflictError(
            f"Document {document_id} is referenced by {ref_count} evaluation job(s) "
            "and cannot be deleted."
        )

    # Step 1: Delete Chroma vectors (tolerate missing)
    try:
        deleted_chroma = delete_chroma_vectors(str(document_id), row.source_type)
        details["chroma_deleted"] = deleted_chroma
    except Exception as exc:
        logger.warning(
            "Chroma deletion reported an issue during document cleanup",
            extra={"document_id": str(document_id), "error": str(exc)},
        )
        details["chroma_warning"] = str(exc)

    # Step 2: Delete DocumentChunk rows
    chunk_count = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document_id)
        .delete()
    )
    details["chunks_deleted"] = chunk_count

    # Step 3: Delete the Document row
    db.delete(row)
    db.flush()

    # Step 4: Delete the local PDF file (tolerate missing)
    if row.file_path:
        pdf_path = Path(row.file_path)
        if pdf_path.exists():
            try:
                pdf_path.unlink()
                details["file_deleted"] = True
            except OSError as exc:
                logger.warning(
                    "Failed to delete local PDF file during document cleanup",
                    extra={
                        "document_id": str(document_id),
                        "file_path": row.file_path,
                        "error": str(exc),
                    },
                )
                details["file_warning"] = str(exc)
        else:
            details["file_missing"] = True
    else:
        details["file_missing"] = True

    db.commit()

    return ReferenceDeleteResponse(
        document_id=document_id,
        deleted=True,
        details=details,
    )





def rebuild_reference_embeddings(
    document_id: uuid.UUID,
    db: Any | None = None,
) -> ReferenceRebuildResponse:
    """Admin-only rebuild of Chroma embeddings from stored chunks for a
    syllabus or curriculum document.
    """
    if db is None:
        raise DocumentNotFoundError(f"Document {document_id} not found")

    from server.modules.embeddings.service import embed_and_store_chunks

    row = db.get(Document, document_id)
    if row is None:
        raise DocumentNotFoundError(f"Document {document_id} not found")

    if not is_reference_source_type(row.source_type):
        raise ReferenceRebuildError(
            f"Rebuild is only supported for syllabus and curriculum documents, "
            f"not {row.source_type}."
        )

    if row.processing_status != "PROCESSED":
        raise ReferenceRebuildError(
            f"Document {document_id} has status '{row.processing_status}'; "
            "only PROCESSED documents can be rebuilt."
        )

    chunks = get_document_chunks(document_id, db=db)
    if not chunks:
        raise ReferenceRebuildError(
            f"Document {document_id} has no stored chunks to rebuild embeddings from."
        )

    upserted = embed_and_store_chunks(chunks)
    if db is not None and upserted:
        _mark_chunks_chroma_stored(db, [chunk.chunk_id for chunk in chunks])
    return ReferenceRebuildResponse(
        document_id=document_id,
        rebuilt=upserted > 0,
        chunk_count=len(chunks),
        details={"chunks_upserted": upserted},
    )


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

    # Direct upload restrictions for retired PDF intake types
    if source_type == "curriculum":
        raise UnsupportedFileTypeError(
            "Direct curriculum document uploads have been retired."
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


def _persist_document(
    db: Any | None,
    response: DocumentResponse,
    file_path: str,
    uploaded_by: uuid.UUID,
    *,
    commit: bool = True,
) -> None:
    _MEM_DOCUMENTS[response.document_id] = response
    _MEM_DOCUMENT_OWNERS[response.document_id] = uploaded_by
    if db is None:
        return

    db_row = db.get(Document, response.document_id)
    if db_row is None:
        db_row = Document(document_id=response.document_id)
    db_row.title = response.title
    db_row.course_title = response.course_title
    db_row.lesson_title = response.lesson_title
    db_row.program = response.program
    db_row.academic_year = response.academic_year
    db_row.course_code = response.course_code
    db_row.source_type = response.source_type
    db_row.policy_area = response.policy_area
    db_row.file_path = file_path
    db_row.uploaded_by = uploaded_by
    db_row.uploaded_at = response.uploaded_at
    db_row.page_count = response.page_count
    db_row.has_ocr_pages = response.has_ocr_pages
    db_row.processing_status = response.processing_status
    db_row.structured_summary = response.structured_summary
    db_row.structured_outline = response.structured_outline
    db_row.section_summaries = response.section_summaries
    db_row.key_facts = response.key_facts
    db_row.processing_warnings = response.processing_warnings
    db_row.evaluation_readiness = response.evaluation_readiness or "PENDING"
    db.add(db_row)
    if commit:
        db.commit()


def _create_upload_intent(
    db: Any,
    *,
    document_id: uuid.UUID,
    title: str,
    course_title: str | None,
    lesson_title: str | None,
    program: str | None,
    source_type: str,
    policy_area: str | None,
    file_path: str,
    uploaded_by: uuid.UUID,
) -> None:
    """Commit a tracked PENDING document before opening its PDF artifact."""
    db.add(
        Document(
            document_id=document_id,
            title=title,
            course_title=course_title,
            lesson_title=lesson_title,
            program=program,
            source_type=source_type,
            policy_area=policy_area,
            file_path=file_path,
            uploaded_by=uploaded_by,
            uploaded_at=datetime.now(UTC),
            processing_status="PENDING",
            evaluation_readiness="PENDING",
        )
    )
    db.commit()


def _mark_interrupted_upload(
    db: Any,
    document_id: uuid.UUID,
    cleanup_succeeded: bool,
) -> None:
    """Record the recoverable state left after an interrupted upload."""
    try:
        row = db.get(Document, document_id)
        if row is not None:
            row.processing_status = "FAILED" if cleanup_succeeded else "CLEANUP_PENDING"
            db.commit()
    except Exception:
        db.rollback()
        logger.exception(
            "Failed to record interrupted upload cleanup state",
            extra={"document_id": str(document_id)},
        )


def _create_upload_marker(document_id: uuid.UUID, file_path: Path) -> Path:
    """Durably claim a no-DB upload artifact before opening the PDF."""
    upload_root_existed = UPLOAD_JOURNAL_ROOT.parent.exists()
    journal_existed = UPLOAD_JOURNAL_ROOT.exists()
    UPLOAD_JOURNAL_ROOT.mkdir(parents=True, exist_ok=True)
    if not upload_root_existed:
        _fsync_directory(UPLOAD_JOURNAL_ROOT.parent.parent)
    if not journal_existed:
        _fsync_directory(UPLOAD_JOURNAL_ROOT.parent)

    marker = UPLOAD_JOURNAL_ROOT / f"{document_id}.pending"
    descriptor = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", closefd=False) as handle:
            handle.write(str(file_path))
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)
    _fsync_directory(UPLOAD_JOURNAL_ROOT)
    return marker


def _fsync_directory(directory: Path) -> None:
    """Persist a directory entry after creating a tracked artifact."""
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _remove_upload_marker(marker: Path) -> None:
    """Remove an ownership marker only after its upload has finalized."""
    try:
        marker.unlink(missing_ok=True)
    except OSError:
        logger.warning(
            "Failed to remove no-DB upload ownership marker",
            extra={"marker": str(marker)},
        )


def _persist_chunks(
    db: Any | None,
    document_id: uuid.UUID,
    chunks: list[Any],
    *,
    commit: bool = True,
) -> None:
    _MEM_CHUNKS[document_id] = chunks
    if db is None:
        return

    if not chunks:
        if commit:
            db.commit()
        return

    rows = [
        DocumentChunk(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            source_type=chunk.source_type,
            agent_domain=chunk.agent_domain,
            page_number=chunk.page_number,
            text=chunk.text,
            token_count=chunk.token_count,
            is_ocr=chunk.is_ocr,
            policy_area=getattr(chunk, "policy_area", None),
            section_ref=getattr(chunk, "section_ref", None),
            chunk_index=getattr(chunk, "chunk_index", None),
        )
        for chunk in chunks
    ]
    db.add_all(rows)
    if commit:
        db.commit()


def get_document_chunks(document_id: uuid.UUID, db: Any | None = None) -> list[Any]:
    if db is not None:
        return (
            db.query(DocumentChunk)
            .filter(DocumentChunk.document_id == document_id)
            .order_by(
                DocumentChunk.chunk_index.asc().nullsfirst(),
                DocumentChunk.page_number.asc(),
                DocumentChunk.created_at.asc(),
            )
            .all()
        )

    return list(_MEM_CHUNKS.get(document_id, []))


def _chunk_responses(chunks: list[Any]) -> list[DocumentChunkResponse]:
    return [
        DocumentChunkResponse(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            source_type=chunk.source_type,
            agent_domain=chunk.agent_domain,
            page_number=chunk.page_number,
            text=chunk.text,
            token_count=chunk.token_count,
            is_ocr=chunk.is_ocr,
            policy_area=getattr(chunk, "policy_area", None),
            section_ref=getattr(chunk, "section_ref", None),
            chunk_index=getattr(chunk, "chunk_index", None),
        )
        for chunk in sorted(
            chunks,
            key=lambda item: (
                item.document_id,
                item.page_number if item.page_number is not None else 0,
                item.chunk_id,
            ),
        )
    ]


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
            document = _MEM_DOCUMENTS.get(document_id)
            source_type = document.source_type if document is not None else None

        if source_type == "slm":
            return 0

        chunks = get_document_chunks(document_id, db=db)
        upserted = embed_and_store_chunks(chunks)
        if db is not None and upserted:
            _mark_chunks_chroma_stored(db, [chunk.chunk_id for chunk in chunks])
        elif db is None and upserted:
            for chunk in chunks:
                if isinstance(chunk, dict):
                    chunk["chroma_stored"] = True
        return upserted
    finally:
        if session is not None:
            session.close()


def _mark_chunks_chroma_stored(db: Any, chunk_ids: list[uuid.UUID]) -> None:
    rows = db.query(DocumentChunk).filter(DocumentChunk.chunk_id.in_(chunk_ids)).all()
    for row in rows:
        row.chroma_stored = True
    db.commit()


def _refresh_tfidf_if_needed(source_type: str) -> None:
    if source_type != "slm":
        return

    slm_chunks: list[Any] = []
    for document_id, metadata in _MEM_DOCUMENTS.items():
        if metadata.source_type == "slm":
            slm_chunks.extend(_MEM_CHUNKS.get(document_id, []))

    _MEM_TFIDF.clear()
    _MEM_TFIDF.update(compute_tfidf_corpus(slm_chunks))


def _cleanup_failed_upload(file_path: Path) -> bool:
    """Remove the uploaded file when preprocessing failed.

    Tries to delete the file up to 3 times (bounded cleanup retries).
    Returns True if deletion succeeds (or file already does not exist),
    and False if deletion fails.
    """
    import time

    for attempt in range(1, 4):
        try:
            if not file_path.exists():
                return True
            file_path.unlink()
            logger.info(
                f"Cleaned up failed upload file (attempt {attempt}/3)",
                extra={"file_path": str(file_path)},
            )
            return True
        except OSError as exc:
            logger.warning(
                f"Failed to clean up failed upload file (attempt {attempt}/3)",
                extra={"file_path": str(file_path), "error": str(exc)},
            )
            if attempt < 3:
                time.sleep(0.05 * attempt)
    return False


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
    if "OCR execution failed" in raw_message or "OCR failed" in raw_message:
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


def get_curriculum_suggestions(
    document_id: uuid.UUID,
    program: str,
    current_user_id: uuid.UUID,
    current_user_role: str,
    db: Any | None = None,
) -> CurriculumSuggestionResponse:
    """Return curriculum suggestions for an SLM document by confirmed program.

    1. Loads the SLM document (ownership check via get_document).
    2. Validates and normalizes the confirmed program.
    3. Queries curriculum documents matching the normalized program.
    4. Separates ready (embedding-ready) and unavailable curricula.
    5. Returns the newest ready curriculum as preferred_suggestion.
    """
    # Step 1: Load the document — access check happens inside get_document
    doc = get_document(document_id, current_user_id, current_user_role, db)
    if doc.source_type != "slm":
        raise ValueError("Curriculum suggestions are only available for SLM documents.")

    # Step 2: Validate and normalize program
    program_stripped = program.strip()
    if not program_stripped:
        raise ValueError("Program must not be empty")

    normalized_program = program_stripped.upper()

    # Step 3: Query matching curriculum documents
    matching_rows: list[Any] = []
    if db is not None:
        from sqlalchemy import func as sa_func

        rows = (
            db.query(Document)
            .filter(
                Document.source_type == "curriculum",
                sa_func.upper(Document.program) == normalized_program,
            )
            .order_by(Document.uploaded_at.desc())
            .all()
        )
        matching_rows = rows
    else:
        matching_rows = [
            d
            for d in _MEM_DOCUMENTS.values()
            if d.source_type == "curriculum"
            and (d.program or "").strip().upper() == normalized_program
        ]
        matching_rows.sort(key=lambda d: d.uploaded_at, reverse=True)

    # Step 4: Separate ready vs unavailable
    ready: list[CurriculumSuggestionItem] = []
    unavailable: list[CurriculumSuggestionItem] = []

    for row in matching_rows:
        if db is not None:
            chunk_count = (
                db.query(DocumentChunk)
                .filter(DocumentChunk.document_id == row.document_id)
                .count()
            )
            from server.modules.embeddings.service import check_chroma_availability

            chroma_available = check_chroma_availability(
                str(row.document_id), "curriculum"
            )
            embedding_ready = (
                row.processing_status == "PROCESSED"
                and chunk_count > 0
                and chroma_available
            )
        else:
            embedding_ready = row.processing_status == "PROCESSED"

        item = CurriculumSuggestionItem(
            document_id=row.document_id,
            title=row.title,
            program=row.program,
            embedding_ready=embedding_ready,
            match_reason="selected_program",
        )

        if embedding_ready:
            ready.append(item)
        else:
            unavailable.append(item)

    # Step 5: Preferred = newest ready curriculum
    preferred = ready[0] if ready else None

    return CurriculumSuggestionResponse(
        document_id=document_id,
        detected_program=doc.program,
        selected_program=program_stripped,
        detected_course_code=doc.course_code,
        detected_academic_year=doc.academic_year,
        detected_lesson_title=doc.lesson_title,
        preferred_suggestion=preferred,
        curriculum_suggestions=ready,
        unavailable_curricula=unavailable,
    )


def recover_cleanup_pending_documents(db_session_factory: Any) -> int:
    """Recover tracked artifacts left by interrupted or failed uploads.

    If cleanup succeeds, updates their status to FAILED.
    Returns the number of successfully cleaned-up documents.
    """
    session = db_session_factory()
    try:
        docs = (
            session.query(Document)
            .filter(
                Document.processing_status.in_(["PENDING", "CLEANUP_PENDING", "FAILED"])
            )
            .all()
        )
        if not docs:
            return 0

        recovered_count = 0
        for doc in docs:
            if not doc.file_path:
                doc.processing_status = "FAILED"
                recovered_count += 1
                continue

            pdf_path = Path(doc.file_path)
            if _cleanup_failed_upload(pdf_path):
                doc.processing_status = "FAILED"
                recovered_count += 1

        if recovered_count > 0:
            session.commit()
            logger.info(
                f"Document cleanup startup recovery successfully cleaned up "
                f"{recovered_count} pending files."
            )
        return recovered_count
    except Exception:
        logger.exception("Failed to recover cleanup-pending documents")
        return 0
    finally:
        session.close()


def recover_no_database_upload_journal() -> int:
    """Remove stale no-DB upload artifacts tracked by ownership markers."""
    if not UPLOAD_JOURNAL_ROOT.exists():
        return 0

    recovered_count = 0
    upload_root = UPLOAD_ROOT.resolve()
    for marker in UPLOAD_JOURNAL_ROOT.glob("*.pending"):
        try:
            file_path = Path(marker.read_text(encoding="utf-8").strip()).resolve()
            if (
                upload_root not in file_path.parents
                or file_path.suffix.lower() != ".pdf"
            ):
                logger.warning(
                    "Ignoring invalid no-DB upload ownership marker",
                    extra={"marker": str(marker)},
                )
                continue
            if _cleanup_failed_upload(file_path):
                _remove_upload_marker(marker)
                recovered_count += 1
        except OSError:
            logger.exception(
                "Failed to recover no-DB upload ownership marker",
                extra={"marker": str(marker)},
            )
    return recovered_count


__all__ = [
    "create_document",
    "embed_document_chunks",
    "get_curriculum_suggestions",
    "get_document",
    "get_syllabus_course_contents",
    "get_document_chunks",
    "get_healthy_policy_allowlist",
    "list_documents",
    "list_reference_documents",
    "list_available_syllabus_references",
    "is_syllabus_reference_ready",
    "process_document_ingestion",
    "stream_document_file",
    "delete_reference_document",
    "rebuild_reference_embeddings",
    "is_reference_source_type",
    "is_policy_source_type",
    "list_policy_documents",
    "delete_policy_document",
    "rebuild_policy_embeddings",
    "recover_cleanup_pending_documents",
    "recover_no_database_upload_journal",
    "validate_policy_chunks",
]
