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
    UnsupportedFileTypeError,
)
from .ingestion import ingest_document
from .models import Document, DocumentChunk
from .preprocessing import prepare_slm_package
from .schemas import (
    SOURCE_TYPES,
    DocumentChunkResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadResponse,
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
            lesson_title=lesson_title,
            program=program,
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
        lesson_title=lesson_title,
        source_type=source_type,
        program=program,
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
        lesson_title=lesson_title,
        source_type=source_type,
        processing_status=status,
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
            if row.uploaded_by != current_user_id:
                raise DocumentNotFoundError(f"Document {document_id} not found")
            return DocumentResponse(
                document_id=row.document_id,
                title=row.title,
                course_title=row.course_title,
                lesson_title=row.lesson_title,
                source_type=row.source_type,
                program=row.program,
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
        query = query.filter(Document.uploaded_by == current_user_id)
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
        if _MEM_DOCUMENT_OWNERS.get(item.document_id) == current_user_id
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


def _validate_upload(
    file: UploadFile, source_type: str, program: str | None, user_role: str = "faculty"
) -> None:
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise UnsupportedFileTypeError("Only PDF uploads are supported")
    if source_type not in SOURCE_TYPES:
        raise UnsupportedFileTypeError(f"Unsupported source_type: {source_type}")
    if source_type == "slm" and not program:
        raise UnsupportedFileTypeError("program is required when source_type is 'slm'")
    # RBAC: only admins can upload institutional knowledge base documents
    if user_role != "admin" and source_type in _ADMIN_ONLY_SOURCE_TYPES:
        raise ForbiddenUploadError(
            f"Only administrators can upload {source_type} documents. "
            "Faculty members can only upload SLM documents."
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
    # Strip any remaining filesystem paths as a safety net
    sanitized = re.sub(r"[/\\][\w./\\_-]+(?:\.pdf|\.db|\.txt)", "[file]", raw_message)
    # Truncate excessively long messages
    if len(sanitized) > 200:
        sanitized = sanitized[:197] + "..."
    return sanitized


__all__ = [
    "create_document",
    "embed_document_chunks",
    "get_document",
    "get_document_chunks",
    "list_documents",
]
