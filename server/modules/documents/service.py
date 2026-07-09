"""Documents service orchestration for upload and retrieval."""

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
from .metadata import detect_metadata
from .models import Document, DocumentChunk
from .preprocessing import prepare_slm_package
from .schemas import (
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
logger = logging.getLogger(__name__)

_MEM_DOCUMENTS: dict[uuid.UUID, DocumentResponse] = {}
_MEM_DOCUMENT_OWNERS: dict[uuid.UUID, uuid.UUID] = {}
_MEM_CHUNKS: dict[uuid.UUID, list[Any]] = {}
_MEM_TFIDF: dict[str, float] = {}


# Restricted source types that only admins can upload
_ADMIN_ONLY_SOURCE_TYPES = {"syllabus", "curriculum", "rubric_sme", "rubric_coord", "rubric_gad", "rubric_itso"}


def is_reference_source_type(source_type: str) -> bool:
    """Return True if the source type is a shared reference (syllabus or curriculum)."""
    return source_type in REFERENCE_SOURCE_TYPES


def _is_document_accessible(document, current_user_id: uuid.UUID) -> bool:
    """Check whether a user may read/access a document row.

    Reference documents (syllabus, curriculum) are shared to all
    authenticated users. SLMs and other types remain owner-only.
    """
    if is_reference_source_type(document.source_type):
        return True
    return document.uploaded_by == current_user_id


def create_document(
    file: UploadFile,
    source_type: str,
    title: str,
    course_title: str | None,
    lesson_title: str | None,
    program: str | None,
    uploaded_by: uuid.UUID,
    user_role: str = "faculty",
    db: Any | None = None,
) -> DocumentUploadResponse:
    """Persist an upload and run Layer-1 ingestion."""

    _validate_upload(file, source_type, program, user_role)
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

    doc_id = uuid.uuid4()
    target_path = UPLOAD_ROOT / f"{doc_id}.pdf"
    with target_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    error_message: str | None = None

    try:
        chunk_data = ingest_document(str(target_path), source_type, str(doc_id))
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
                "original_filename": file.filename,
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
                "original_filename": file.filename,
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
    effective_program = program
    if effective_program is None and detected_metadata.get("program"):
        effective_program = detected_metadata["program"]
    # Normalize program for curriculum documents to uppercase/trimmed
    if source_type == "curriculum" and effective_program is not None:
        effective_program = effective_program.strip().upper()
    effective_lesson_title = lesson_title
    if effective_lesson_title is None and detected_metadata.get("lesson_title"):
        effective_lesson_title = detected_metadata["lesson_title"]
    detected_academic_year = detected_metadata.get("academic_year")
    detected_course_code = detected_metadata.get("course_code")
    # ─────────────────────────────────────────────────────────────────

    if status == "FAILED":
        _cleanup_failed_upload(target_path)

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

    runtime_db = db
    runtime_session = None
    if runtime_db is None and get_settings().database_configured:
        runtime_session = get_session_factory()()
        runtime_db = runtime_session

    try:
        _persist_document(runtime_db, response, str(target_path), uploaded_by)
        _persist_chunks(runtime_db, doc_id, chunk_data)
    finally:
        if runtime_session is not None:
            runtime_session.close()

    _refresh_tfidf_if_needed(source_type)

    return DocumentUploadResponse(
        document_id=doc_id,
        title=title,
        course_title=course_title,
        lesson_title=effective_lesson_title,
        source_type=source_type,
        processing_status=status,
        academic_year=detected_academic_year,
        course_code=detected_course_code,
        structured_summary=structured_summary,
        evaluation_readiness=evaluation_readiness,
        error_message=error_message,
    )


def get_document(
    document_id: uuid.UUID,
    current_user_id: uuid.UUID,
    current_user_role: str,
    db: Any | None = None,
) -> DocumentResponse:
    if db is not None:
        row = db.get(Document, document_id)
        if row is not None:
            if not _is_document_accessible(row, current_user_id):
                raise DocumentNotFoundError(f"Document {document_id} not found")
            return DocumentResponse(
                document_id=row.document_id,
                title=row.title,
                course_title=row.course_title,
                lesson_title=row.lesson_title,
                source_type=row.source_type,
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
    owner_id = _MEM_DOCUMENT_OWNERS.get(document_id)
    if owner_id != current_user_id:
        raise DocumentNotFoundError(f"Document {document_id} not found")
    return fallback.model_copy(
        update={"chunks": _chunk_responses(get_document_chunks(document_id, db=None))}
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
        if source_type:
            query = query.filter(Document.source_type == source_type)
        if program:
            query = query.filter(Document.program == program)
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
        )
    ]
    if source_type:
        mem_items = [item for item in mem_items if item.source_type == source_type]
    if program:
        mem_items = [item for item in mem_items if item.program == program]
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


def stream_document_file(
    document_id: uuid.UUID,
    current_user_id: uuid.UUID,
    db: Any | None = None,
) -> Path:
    """Return the local file path for a document, enforcing access rules.

    Reference documents are shared to authenticated users.
    SLMs remain owner-only.
    Raises DocumentNotFoundError if the document is not found, not
    accessible, or the local file is missing.
    """
    if db is None:
        raise DocumentNotFoundError(f"Document {document_id} not found")

    row = db.get(Document, document_id)
    if row is None:
        raise DocumentNotFoundError(f"Document {document_id} not found")

    if not _is_document_accessible(row, current_user_id):
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

    from server.modules.evaluations.models import EvaluationJob
    from server.modules.embeddings.service import delete_chroma_vectors

    row = db.get(Document, document_id)
    if row is None:
        raise DocumentNotFoundError(f"Document {document_id} not found")

    details: dict[str, object] = {}

    # Step 0: Validate source type — only reference documents can be deleted here
    if not is_reference_source_type(row.source_type):
        raise ReferenceDeleteInvalidTypeError(
            f"Document {document_id} has source_type='{row.source_type}'; "
            "only syllabus and curriculum documents can be deleted through this endpoint."
        )

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
                    extra={"document_id": str(document_id), "file_path": row.file_path, "error": str(exc)},
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
    file: UploadFile, source_type: str, program: str | None, user_role: str = "faculty"
) -> None:
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise UnsupportedFileTypeError("Only PDF uploads are supported")
    if source_type not in SOURCE_TYPES:
        raise UnsupportedFileTypeError(f"Unsupported source_type: {source_type}")
    # RBAC: only admins can upload institutional knowledge base documents
    if user_role != "admin" and source_type in _ADMIN_ONLY_SOURCE_TYPES:
        raise ForbiddenUploadError(
            f"Only administrators can upload {source_type} documents. "
            "Faculty members can only upload SLM documents."
        )
    # Curriculum documents require a program for program-driven suggestion
    if source_type == "curriculum" and not (program and program.strip()):
        raise UnsupportedFileTypeError(
            "Program is required for curriculum documents."
        )


def _persist_document(
    db: Any | None,
    response: DocumentResponse,
    file_path: str,
    uploaded_by: uuid.UUID,
) -> None:
    _MEM_DOCUMENTS[response.document_id] = response
    _MEM_DOCUMENT_OWNERS[response.document_id] = uploaded_by
    if db is None:
        return

    db_row = Document(
        document_id=response.document_id,
        title=response.title,
        course_title=response.course_title,
        lesson_title=response.lesson_title,
        program=response.program,
        academic_year=response.academic_year,
        course_code=response.course_code,
        source_type=response.source_type,
        file_path=file_path,
        uploaded_by=uploaded_by,
        uploaded_at=response.uploaded_at,
        page_count=response.page_count,
        has_ocr_pages=response.has_ocr_pages,
        processing_status=response.processing_status,
        structured_summary=response.structured_summary,
        structured_outline=response.structured_outline,
        section_summaries=response.section_summaries,
        key_facts=response.key_facts,
        processing_warnings=response.processing_warnings,
        evaluation_readiness=response.evaluation_readiness or "PENDING",
    )
    db.add(db_row)
    db.commit()


def _persist_chunks(db: Any | None, document_id: uuid.UUID, chunks: list[Any]) -> None:
    _MEM_CHUNKS[document_id] = chunks
    if db is None:
        return

    if not chunks:
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
        )
        for chunk in chunks
    ]
    db.add_all(rows)
    db.commit()


def get_document_chunks(document_id: uuid.UUID, db: Any | None = None) -> list[Any]:
    if db is not None:
        return (
            db.query(DocumentChunk)
            .filter(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.page_number.asc(), DocumentChunk.created_at.asc())
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


def _cleanup_failed_upload(file_path: Path) -> None:
    """Remove the uploaded file when preprocessing failed."""
    try:
        if file_path.exists():
            file_path.unlink()
            logger.info(
                "Cleaned up failed upload file",
                extra={"file_path": str(file_path)},
            )
    except OSError as exc:
        logger.warning(
            "Failed to clean up failed upload file",
            extra={"file_path": str(file_path), "error": str(exc)},
        )


def _sanitize_error(raw_message: str) -> str:
    """Strip internal details (file paths, stack traces) from error messages."""
    # Map known internal messages to user-facing equivalents
    if raw_message.startswith("File not found:"):
        return "The uploaded file could not be processed."
    if raw_message == "PyMuPDF is not installed":
        return "Document processing is unavailable. Please contact support."
    if raw_message == "Failed to extract document pages":
        return "The PDF could not be read. It may be corrupted or unsupported."
    if raw_message.startswith("This PDF appears to be scanned"):
        return (
            "This PDF appears to be scanned (image-based) and could not be "
            "read. Ask an administrator to enable OCR, or upload a "
            "text-based PDF."
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


__all__ = [
    "create_document",
    "embed_document_chunks",
    "get_curriculum_suggestions",
    "get_document",
    "get_document_chunks",
    "list_documents",
    "list_reference_documents",
    "stream_document_file",
    "delete_reference_document",
    "rebuild_reference_embeddings",
    "is_reference_source_type",
]
