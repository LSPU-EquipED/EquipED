"""Pre-execution validation and admission checks for standalone syllabus alignment."""

from __future__ import annotations

import uuid
from typing import Any

from server.modules.documents.models import Document, DocumentChunk
from server.modules.documents.references import is_syllabus_reference_ready
from server.modules.syllabus_alignment.exceptions import (
    InvalidSyllabusAlignmentTargetError,
    SyllabusAlignmentNotFoundError,
)
from sqlalchemy import func


def require_owned_slm(db: Any, document_id: uuid.UUID, owner_id: uuid.UUID) -> Document:
    """Validate that the document exists, is an SLM, and belongs to the owner."""
    document = db.get(Document, document_id)
    if (
        document is None
        or document.source_type != "slm"
        or document.uploaded_by != owner_id
    ):
        raise SyllabusAlignmentNotFoundError("SLM document not found")
    return document


def validate_syllabus_alignment_targets(
    db: Any,
    *,
    slm_document_id: uuid.UUID,
    syllabus_document_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> tuple[Document, Document]:
    """Validate owned processed SLM with chunks and retrieval-ready syllabus."""
    slm = require_owned_slm(db, slm_document_id, owner_id)
    chunk_count = (
        db.query(func.count(DocumentChunk.chunk_id))
        .filter(DocumentChunk.document_id == slm.document_id)
        .scalar()
    )
    if slm.processing_status != "PROCESSED" or not chunk_count:
        raise InvalidSyllabusAlignmentTargetError(
            "The selected SLM must finish processing before alignment."
        )

    syllabus = db.get(Document, syllabus_document_id)
    if syllabus is None or syllabus.source_type != "syllabus":
        raise InvalidSyllabusAlignmentTargetError(
            "Select a syllabus from the shared Reference Library."
        )
    ready, _content_count = is_syllabus_reference_ready(syllabus, db)
    if not ready:
        raise InvalidSyllabusAlignmentTargetError(
            "The selected syllabus is not retrieval-ready. Ask an admin to "
            "finish processing or rebuild its embeddings."
        )

    return slm, syllabus


__all__ = [
    "require_owned_slm",
    "validate_syllabus_alignment_targets",
]
