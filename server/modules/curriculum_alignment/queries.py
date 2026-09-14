"""Queries and response mapping for curriculum alignment checks."""

from __future__ import annotations

import uuid
from typing import Any

from server.modules.curriculum.models import Course

from .admission import require_owned_document
from .document_text import DocumentPage, load_document_pages
from .exceptions import AlignmentCheckNotFoundError
from .models import CurriculumAlignmentCheck
from .schemas import AlignmentCheckResponse


def get_alignment_check(
    check_id: uuid.UUID, current_user_id: uuid.UUID, db: Any
) -> CurriculumAlignmentCheck:
    check = db.get(CurriculumAlignmentCheck, check_id)
    if check is None:
        raise AlignmentCheckNotFoundError(f"Alignment check {check_id} not found")
    require_owned_document(check.document_id, current_user_id, db)
    return check


def get_document_pages_for_check(
    check_id: uuid.UUID, current_user_id: uuid.UUID, db: Any
) -> list[DocumentPage]:
    """All persisted pages for the check's document (reading pane)."""
    check = get_alignment_check(check_id, current_user_id, db)
    return load_document_pages(db, check.document_id)


def get_coverage_metadata(check: CurriculumAlignmentCheck) -> dict[str, Any]:
    """Coverage metadata for a persisted check.

    Checks created before Phase 2B persisted no provenance, so their coverage
    is unknown; they report scope ``legacy_unknown``.
    """
    coverage = (check.provenance or {}).get("coverage")
    if not coverage:
        return {
            "scope": "legacy_unknown",
            "total_pages": None,
            "evaluated_pages": None,
            "total_chars": None,
            "evaluated_chars": None,
            "strategy": None,
        }
    return coverage


def list_alignment_checks(
    *,
    current_user_id: uuid.UUID,
    page: int,
    page_size: int,
    db: Any,
) -> tuple[list[dict[str, Any]], int]:
    """Return (items, total) of this user's past checks, newest first.

    Joins CurriculumAlignmentCheck -> Document (ownership filter + title)
    -> Course (title). Deliberately excludes objective_results/evidence --
    those are only fetched per-check via get_alignment_check.
    """
    from server.modules.documents.models import Document

    query = (
        db.query(CurriculumAlignmentCheck, Document.title, Course.course_title)
        .join(Document, CurriculumAlignmentCheck.document_id == Document.document_id)
        .join(Course, CurriculumAlignmentCheck.course_id == Course.course_id)
        .filter(Document.uploaded_by == current_user_id)
        .order_by(
            CurriculumAlignmentCheck.run_at.desc(),
            CurriculumAlignmentCheck.check_id.desc(),
        )
    )
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    items = [
        {
            "check_id": check.check_id,
            "document_id": check.document_id,
            "document_title": document_title,
            "course_id": check.course_id,
            "course_title": course_title,
            "run_at": check.run_at,
            "success": check.success,
            "error_message": check.error_message,
            "summary": check.summary,
        }
        for check, document_title, course_title in rows
    ]
    return items, total


def to_alignment_check_response(
    check: CurriculumAlignmentCheck, db: Any
) -> AlignmentCheckResponse:
    """Map a CurriculumAlignmentCheck model instance to its schema response."""
    course = db.get(Course, check.course_id)
    return AlignmentCheckResponse(
        check_id=check.check_id,
        document_id=check.document_id,
        course_id=check.course_id,
        course_title=course.course_title if course else "",
        run_at=check.run_at,
        model_name=check.model_name,
        objective_results=check.objective_results,
        summary=check.summary,
        success=check.success,
        error_message=check.error_message,
    )


__all__ = [
    "get_alignment_check",
    "get_document_pages_for_check",
    "get_coverage_metadata",
    "list_alignment_checks",
    "to_alignment_check_response",
]
