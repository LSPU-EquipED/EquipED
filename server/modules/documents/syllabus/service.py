"""Reference document lifecycle: syllabus library, readiness, and
delete/rebuild operations.

Reference documents (syllabus) are institution-shared: they are
uploaded by admins, embedded into Chroma, and consumed by evaluations and
alignment. This module keeps that lifecycle out of the general document
service. Policy documents are intentionally separate (``policy.service``).
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from server.modules.auth.models import User, UserRole
from server.modules.embeddings.service import (
    check_chroma_availability,
    delete_chroma_vectors,
    embed_and_store_chunks,
)
from server.modules.evaluations.document_references import count_document_references

from .. import persistence
from ..access import get_document, is_reference_source_type
from ..exceptions import (
    DocumentNotFoundError,
    ReferenceDeleteConflictError,
    ReferenceDeleteInvalidTypeError,
    ReferenceRebuildError,
)
from ..models import Document, DocumentChunk
from ..schemas import (
    REFERENCE_SOURCE_TYPES,
    ReferenceDeleteResponse,
    ReferenceLibraryItem,
    ReferenceLibraryResponse,
    ReferenceRebuildResponse,
    SyllabusCourseContentItem,
    SyllabusCourseContentsResponse,
    SyllabusReferenceOption,
    SyllabusReferenceOptionsResponse,
)

logger = logging.getLogger(__name__)


def get_syllabus_course_contents(
    document_id: uuid.UUID,
    current_user_id: uuid.UUID,
    current_user_role: str,
    db: Any | None = None,
):
    """Return authoritative persisted Course Contents chunks for a syllabus."""
    document = get_document(document_id, current_user_id, current_user_role, db=db)
    if document.source_type != "syllabus":
        raise ValueError("Course contents are only available for syllabus documents.")
    chunks = sorted(
        (
            chunk
            for chunk in persistence.get_document_chunks(document_id, db=db)
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


def list_reference_documents(
    db: Any | None = None,
) -> ReferenceLibraryResponse:
    """Admin-only listing of syllabus documents with computed health."""
    if db is None:
        return ReferenceLibraryResponse(items=[], total=0)

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

    return (
        check_chroma_availability(str(document.document_id), "syllabus"),
        content_count,
    )


def list_available_syllabus_references(db: Any):
    """Return shared syllabi that can be used by the alignment retrieval path."""
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

    row = db.get(Document, document_id)
    if row is None:
        raise DocumentNotFoundError(f"Document {document_id} not found")

    details: dict[str, object] = {}

    # Step 0: Validate source type — only reference documents can be deleted here
    if not is_reference_source_type(row.source_type):
        err_msg = (
            f"Document {document_id} has source_type='{row.source_type}'; "
            "only syllabus documents can be deleted "
            "through this endpoint."
        )
        raise ReferenceDeleteInvalidTypeError(err_msg)

    # Step 1: Check for evaluation job references
    ref_count = count_document_references(document_id, db)
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
    syllabus document.
    """
    if db is None:
        raise DocumentNotFoundError(f"Document {document_id} not found")

    row = db.get(Document, document_id)
    if row is None:
        raise DocumentNotFoundError(f"Document {document_id} not found")

    if not is_reference_source_type(row.source_type):
        raise ReferenceRebuildError(
            f"Rebuild is only supported for syllabus documents, not {row.source_type}."
        )

    if row.processing_status != "PROCESSED":
        raise ReferenceRebuildError(
            f"Document {document_id} has status '{row.processing_status}'; "
            "only PROCESSED documents can be rebuilt."
        )

    chunks = persistence.get_document_chunks(document_id, db=db)
    if not chunks:
        raise ReferenceRebuildError(
            f"Document {document_id} has no stored chunks to rebuild embeddings from."
        )

    upserted = embed_and_store_chunks(chunks)
    if db is not None and upserted:
        persistence.mark_chunks_chroma_stored(db, [chunk.chunk_id for chunk in chunks])
    return ReferenceRebuildResponse(
        document_id=document_id,
        rebuilt=upserted > 0,
        chunk_count=len(chunks),
        details={"chunks_upserted": upserted},
    )


__all__ = [
    "get_syllabus_course_contents",
    "list_reference_documents",
    "is_syllabus_reference_ready",
    "list_available_syllabus_references",
    "delete_reference_document",
    "rebuild_reference_embeddings",
]
