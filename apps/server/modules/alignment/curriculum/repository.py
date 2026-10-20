"""Persistence and database mutations for curriculum alignment checks."""

from __future__ import annotations

import uuid
from typing import Any

from .admission import require_owned_document
from .exceptions import AlignmentCheckNotFoundError
from .models import CurriculumAlignmentCheck
from .results import EvaluatedAlignmentResult


def persist_alignment_check(
    *,
    db: Any,
    document_id: uuid.UUID,
    course_id: uuid.UUID,
    result: EvaluatedAlignmentResult,
) -> CurriculumAlignmentCheck:
    """Construct and commit a check row from an EvaluatedAlignmentResult."""
    check = CurriculumAlignmentCheck(
        document_id=document_id,
        course_id=course_id,
        model_name=result.model_name,
        objective_results=result.objective_results,
        summary=result.summary,
        success=result.success,
        error_message=result.error_message,
        provenance=result.provenance,
    )
    db.add(check)
    db.commit()
    return check


def delete_alignment_check(
    check_id: uuid.UUID, current_user_id: uuid.UUID, db: Any
) -> None:
    """Delete one check; check must exist and document belongs to caller."""
    check = db.get(CurriculumAlignmentCheck, check_id)
    if check is None:
        raise AlignmentCheckNotFoundError(f"Alignment check {check_id} not found")
    require_owned_document(check.document_id, current_user_id, db)
    db.delete(check)
    db.commit()


__all__ = [
    "persist_alignment_check",
    "delete_alignment_check",
]
