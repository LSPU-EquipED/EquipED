"""Document persistence and in-memory state."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from .models import Document, DocumentChunk
from .schemas import DocumentResponse

_MEM_DOCUMENTS: dict[uuid.UUID, DocumentResponse] = {}
_MEM_DOCUMENT_OWNERS: dict[uuid.UUID, uuid.UUID] = {}
_MEM_CHUNKS: dict[uuid.UUID, list[Any]] = {}
logger = logging.getLogger(__name__)


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


def mark_chunks_chroma_stored(db: Any, chunk_ids: list[uuid.UUID]) -> None:
    rows = db.query(DocumentChunk).filter(DocumentChunk.chunk_id.in_(chunk_ids)).all()
    for row in rows:
        row.chroma_stored = True
    db.commit()


__all__ = ["get_document_chunks", "mark_chunks_chroma_stored"]
