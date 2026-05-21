"""Documents service orchestration for upload and retrieval."""

from __future__ import annotations

import shutil
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from server.core.config import get_settings
from server.core.database import get_session_factory

from .exceptions import (
    DocumentNotFoundError,
    ExtractionFailedError,
    UnsupportedFileTypeError,
)
from .ingestion import ingest_document
from .models import Document, DocumentChunk
from .preprocessing import prepare_slm_package
from .schemas import (
    SOURCE_TYPES,
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadResponse,
)
from .tfidf import compute_tfidf_corpus
from server.modules.embeddings.service import embed_and_store_chunks

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
UPLOAD_ROOT = _PROJECT_ROOT / "uploads"
logger = logging.getLogger(__name__)

_MEM_DOCUMENTS: dict[uuid.UUID, DocumentResponse] = {}
_MEM_DOCUMENT_OWNERS: dict[uuid.UUID, uuid.UUID] = {}
_MEM_CHUNKS: dict[uuid.UUID, list[Any]] = {}
_MEM_TFIDF: dict[str, float] = {}


def create_document(
    file: UploadFile,
    source_type: str,
    title: str,
    course_title: str | None,
    lesson_title: str | None,
    program: str | None,
    uploaded_by: uuid.UUID,
    db: Any | None = None,
) -> DocumentUploadResponse:
    """Persist an upload and run Layer-1 ingestion."""

    _validate_upload(file, source_type, program)
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

    doc_id = uuid.uuid4()
    target_path = UPLOAD_ROOT / f"{doc_id}.pdf"
    with target_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        chunk_data = ingest_document(str(target_path), source_type, str(doc_id))
        page_count = max((chunk.page_number for chunk in chunk_data), default=0)
        has_ocr_pages = any(chunk.is_ocr for chunk in chunk_data)
        status = "PROCESSED" if chunk_data else "FAILED"
    except ExtractionFailedError as exc:
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
        page_count = None
        has_ocr_pages = False
        status = "FAILED"
        chunk_data = []

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

    _persist_document(db, response, str(target_path), uploaded_by)
    _persist_chunks(db, doc_id, chunk_data)
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
            )

    fallback = _MEM_DOCUMENTS.get(document_id)
    if fallback is None:
        raise DocumentNotFoundError(f"Document {document_id} not found")
    owner_id = _MEM_DOCUMENT_OWNERS.get(document_id)
    if owner_id != current_user_id:
        raise DocumentNotFoundError(f"Document {document_id} not found")
    return fallback


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


def _validate_upload(file: UploadFile, source_type: str, program: str | None) -> None:
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise UnsupportedFileTypeError("Only PDF uploads are supported")
    if source_type not in SOURCE_TYPES:
        raise UnsupportedFileTypeError(f"Unsupported source_type: {source_type}")
    if source_type == "slm" and not program:
        raise UnsupportedFileTypeError("program is required when source_type is 'slm'")


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
    if db is None or not chunks:
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


__all__ = [
    "create_document",
    "embed_document_chunks",
    "get_document",
    "get_document_chunks",
    "list_documents",
]
