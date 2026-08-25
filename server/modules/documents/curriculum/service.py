"""Curriculum document service: readiness validation and helpers."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from server.modules.auth.models import User, UserRole
from server.modules.embeddings.service import check_chroma_availability

from ..metadata import canonicalize_supported_program
from ..models import Document, DocumentChunk

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CurriculumReadiness:
    is_ready: bool
    document_id: uuid.UUID
    program: str | None
    chunk_count: int
    chroma_available: bool
    is_admin: bool = False
    reason: str | None = None


def check_curriculum_readiness(
    document: Document | uuid.UUID,
    program: str,
    db: Any,
) -> CurriculumReadiness:
    """Validate curriculum readiness against database and live Chroma vectors.

    Public callable for suggestions and evaluation admission.
    Requires:
    1. Document exists and has source_type == 'curriculum'
    2. Document was uploaded by an administrator (User.role == ADMIN)
    3. Document program matches canonical target program ('BSCS' or 'BSInfoTech')
    4. processing_status == 'PROCESSED'
    5. Persisted chunks count > 0 in SQL
    6. Live vectors exist in local Chroma reference collection (not just SQL flag)
    """
    if isinstance(document, uuid.UUID):
        doc_id = document
        doc = db.get(Document, doc_id) if hasattr(db, "get") else None
        if doc is None and hasattr(db, "query"):
            doc = db.query(Document).filter(Document.document_id == doc_id).first()
    else:
        doc = document
        doc_id = doc.document_id if doc else uuid.uuid4()

    if doc is None or doc.source_type != "curriculum":
        return CurriculumReadiness(
            is_ready=False,
            document_id=doc_id,
            program=getattr(doc, "program", None),
            chunk_count=0,
            chroma_available=False,
            is_admin=False,
            reason="Document not found or is not a curriculum reference",
        )

    # 1. Check admin provenance
    if doc.uploaded_by is None:
        return CurriculumReadiness(
            is_ready=False,
            document_id=doc.document_id,
            program=doc.program,
            chunk_count=0,
            chroma_available=False,
            is_admin=False,
            reason="Curriculum lacks uploader provenance",
        )

    uploader = None
    if hasattr(db, "get"):
        uploader = db.get(User, doc.uploaded_by)
    if uploader is None and hasattr(db, "query"):
        uploader = db.query(User).filter(User.user_id == doc.uploaded_by).first()

    if uploader is None or uploader.role != UserRole.ADMIN:
        return CurriculumReadiness(
            is_ready=False,
            document_id=doc.document_id,
            program=doc.program,
            chunk_count=0,
            chroma_available=False,
            is_admin=False,
            reason="Curriculum was not uploaded by an administrator",
        )

    # 2. Check canonical program match
    target_canonical = canonicalize_supported_program(program)
    doc_canonical = canonicalize_supported_program(doc.program)
    if not target_canonical or doc_canonical != target_canonical:
        return CurriculumReadiness(
            is_ready=False,
            document_id=doc.document_id,
            program=doc.program,
            chunk_count=0,
            chroma_available=False,
            is_admin=True,
            reason=(
                f"Curriculum program '{doc.program}' does not match "
                f"requested program '{program}'"
            ),
        )

    # 3. Check processing status
    if doc.processing_status != "PROCESSED":
        return CurriculumReadiness(
            is_ready=False,
            document_id=doc.document_id,
            program=doc.program,
            chunk_count=0,
            chroma_available=False,
            is_admin=True,
            reason=(
                f"Curriculum processing status is '{doc.processing_status}', "
                "expected 'PROCESSED'"
            ),
        )

    # 4. Check chunks in SQL
    chunk_count = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == doc.document_id)
        .count()
        if hasattr(db, "query")
        else 0
    )
    if chunk_count == 0:
        return CurriculumReadiness(
            is_ready=False,
            document_id=doc.document_id,
            program=doc.program,
            chunk_count=0,
            chroma_available=False,
            is_admin=True,
            reason="Curriculum has no persisted chunks in SQL",
        )

    # 5. Check live Chroma availability
    chroma_available = check_chroma_availability(str(doc.document_id), "curriculum")
    if not chroma_available:
        return CurriculumReadiness(
            is_ready=False,
            document_id=doc.document_id,
            program=doc.program,
            chunk_count=chunk_count,
            chroma_available=False,
            is_admin=True,
            reason="Curriculum has no live local Chroma vectors",
        )

    return CurriculumReadiness(
        is_ready=True,
        document_id=doc.document_id,
        program=doc.program,
        chunk_count=chunk_count,
        chroma_available=True,
        is_admin=True,
        reason=None,
    )


__all__ = [
    "CurriculumReadiness",
    "check_curriculum_readiness",
]
