"""Documents service orchestration for upload and retrieval."""

from __future__ import annotations

import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from .exceptions import (
    DocumentNotFoundError,
    ExtractionFailedError,
    UnsupportedFileTypeError,
)
from .ingestion import ingest_document
from .models import Document, DocumentChunk
from .schemas import (
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadResponse,
    SOURCE_TYPES,
)
from .tfidf import compute_tfidf_corpus

UPLOAD_ROOT = Path("uploads")

_MEM_DOCUMENTS: dict[uuid.UUID, DocumentResponse] = {}
_MEM_CHUNKS: dict[uuid.UUID, list[Any]] = {}
_MEM_TFIDF: dict[str, float] = {}


def create_document(
    file: UploadFile,
    source_type: str,
    title: str,
    program: str | None,
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
    except ExtractionFailedError:
        page_count = None
        has_ocr_pages = False
        status = "FAILED"
        chunk_data = []

    uploaded_at = datetime.now(UTC)
    response = DocumentResponse(
        document_id=doc_id,
        title=title,
        source_type=source_type,
        program=program,
        page_count=page_count,
        processing_status=status,
        has_ocr_pages=has_ocr_pages,
        uploaded_at=uploaded_at,
    )

    _persist_document(db, response, str(target_path))
    _persist_chunks(db, doc_id, chunk_data)
    _refresh_tfidf_if_needed(source_type)

    return DocumentUploadResponse(
        document_id=doc_id,
        title=title,
        source_type=source_type,
        processing_status=status,
    )


def get_document(document_id: uuid.UUID, db: Any | None = None) -> DocumentResponse:
    if db is not None:
        row = db.get(Document, document_id)
        if row is not None:
            return DocumentResponse(
                document_id=row.document_id,
                title=row.title,
                source_type=row.source_type,
                program=row.program,
                page_count=row.page_count,
                processing_status=row.processing_status,
                has_ocr_pages=row.has_ocr_pages,
                uploaded_at=row.uploaded_at,
            )

    fallback = _MEM_DOCUMENTS.get(document_id)
    if fallback is None:
        raise DocumentNotFoundError(f"Document {document_id} not found")
    return fallback


def list_documents(
    source_type: str | None,
    program: str | None,
    page: int,
    page_size: int,
    db: Any | None = None,
) -> DocumentListResponse:
    items: list[DocumentResponse]
    if db is not None:
        query = db.query(Document)
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
                source_type=row.source_type,
                program=row.program,
                page_count=row.page_count,
                processing_status=row.processing_status,
                has_ocr_pages=row.has_ocr_pages,
                uploaded_at=row.uploaded_at,
            )
            for row in rows
        ]
        return DocumentListResponse(items=items, total=total, page=page, page_size=page_size)

    mem_items = list(_MEM_DOCUMENTS.values())
    if source_type:
        mem_items = [item for item in mem_items if item.source_type == source_type]
    if program:
        mem_items = [item for item in mem_items if item.program == program]
    total = len(mem_items)
    start = (page - 1) * page_size
    end = start + page_size
    return DocumentListResponse(items=mem_items[start:end], total=total, page=page, page_size=page_size)


def _validate_upload(file: UploadFile, source_type: str, program: str | None) -> None:
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise UnsupportedFileTypeError("Only PDF uploads are supported")
    if source_type not in SOURCE_TYPES:
        raise UnsupportedFileTypeError(f"Unsupported source_type: {source_type}")
    if source_type == "slm" and not program:
        raise UnsupportedFileTypeError("program is required when source_type is 'slm'")


def _persist_document(db: Any | None, response: DocumentResponse, file_path: str) -> None:
    _MEM_DOCUMENTS[response.document_id] = response
    if db is None:
        return

    db_row = Document(
        document_id=response.document_id,
        title=response.title,
        program=response.program,
        source_type=response.source_type,
        file_path=file_path,
        uploaded_at=response.uploaded_at,
        page_count=response.page_count,
        has_ocr_pages=response.has_ocr_pages,
        processing_status=response.processing_status,
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


def _refresh_tfidf_if_needed(source_type: str) -> None:
    if source_type != "slm":
        return

    slm_chunks: list[Any] = []
    for document_id, metadata in _MEM_DOCUMENTS.items():
        if metadata.source_type == "slm":
            slm_chunks.extend(_MEM_CHUNKS.get(document_id, []))

    _MEM_TFIDF.clear()
    _MEM_TFIDF.update(compute_tfidf_corpus(slm_chunks))


__all__ = ["create_document", "get_document", "list_documents"]
