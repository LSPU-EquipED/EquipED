"""Document access and query operations."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from . import persistence
from .exceptions import DocumentNotFoundError
from .metadata import canonicalize_supported_program
from .models import Document
from .schemas import (
    POLICY_SOURCE_TYPES,
    REFERENCE_SOURCE_TYPES,
    DocumentChunkResponse,
    DocumentListResponse,
    DocumentResponse,
)


def is_reference_source_type(source_type: str) -> bool:
    """Return True if the source type is an active shared reference (syllabus)."""
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

    Reference documents (syllabus) are shared to all
    authenticated users. Policy documents are admin-only — faculty
    requests are denied without existence leakage. Legacy curriculum
    rows are maintenance-only and never accessible here, even to their
    original uploader. SLMs and other types remain owner-only.
    """
    if document.source_type == "curriculum":
        return False
    if is_reference_source_type(document.source_type):
        return True
    if is_policy_source_type(document.source_type):
        return current_user_role == "admin"
    if current_user_id is not None:
        return document.uploaded_by == current_user_id
    return False


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
                chunks=_chunk_responses(
                    persistence.get_document_chunks(document_id, db=db)
                ),
            )

    fallback = persistence._MEM_DOCUMENTS.get(document_id)
    if fallback is None:
        raise DocumentNotFoundError(f"Document {document_id} not found")
    if fallback.source_type == "curriculum":
        raise DocumentNotFoundError(f"Document {document_id} not found")
    if is_policy_source_type(fallback.source_type):
        if current_user_role != "admin":
            raise DocumentNotFoundError(f"Document {document_id} not found")
    elif is_reference_source_type(fallback.source_type):
        pass  # shared to all
    else:
        owner_id = persistence._MEM_DOCUMENT_OWNERS.get(document_id)
        if owner_id != current_user_id:
            raise DocumentNotFoundError(f"Document {document_id} not found")
    return fallback.model_copy(
        update={
            "chunks": _chunk_responses(
                persistence.get_document_chunks(document_id, db=None)
            )
        }
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
            query = query.filter(Document.source_type.notin_(POLICY_SOURCE_TYPES))
        # Legacy curriculum rows are maintenance-only — never exposed via list
        query = query.filter(Document.source_type != "curriculum")
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

    mem_items = list(persistence._MEM_DOCUMENTS.values())
    mem_items = [
        item
        for item in mem_items
        if (
            item.source_type != "curriculum"
            and (
                persistence._MEM_DOCUMENT_OWNERS.get(item.document_id)
                == current_user_id
                or is_reference_source_type(item.source_type)
                or (
                    is_policy_source_type(item.source_type)
                    and current_user_role == "admin"
                )
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


def stream_document_file(
    document_id: uuid.UUID,
    current_user_id: uuid.UUID,
    current_user_role: str | None = None,
    db: Any | None = None,
) -> Path:
    """Return the local file path for a document, enforcing access rules.

    Reference documents (syllabus) are shared to authenticated users.
    Policy documents are admin-only. Legacy curriculum rows are
    maintenance-only and never streamed here.
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


__all__ = [
    "get_document",
    "is_policy_source_type",
    "is_reference_source_type",
    "list_documents",
    "stream_document_file",
]
