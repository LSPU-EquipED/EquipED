"""Orchestration for the curriculum alignment check pipeline."""

from __future__ import annotations

import uuid
from typing import Any

from server.core.llm import get_llm_client
from server.modules.curriculum.service import get_course, get_mapped_objectives

from .admission import (
    enforce_recheck_cooldown,
    require_owned_document,
    validate_course_program,
    validate_document_for_alignment,
    validate_objective_programs,
)
from .alignment_check import run_alignment_check
from .alignment_runtime import RETRY_BACKOFF_SECONDS
from .document_text import load_document_pages, select_pages_within_budget
from .exceptions import (
    CourseNotFoundError,
    NoCurriculumMapError,
    NoUsableDocumentTextError,
)
from .models import CurriculumAlignmentCheck
from .repository import persist_alignment_check
from .results import build_failed_result, build_successful_result

# Safety cap on the joined SLM text sent to the LLM. Mirrors the same
# budget-guard discipline as agents/base.py's prompt packing (design spec
# section 7: "SLM text exceeds prompt context budget"), just simpler since
# this pipeline sends one document's text rather than ranked chunks.
_MAX_SLM_TEXT_CHARS = 6000


def run_curriculum_alignment_check(
    *,
    document_id: uuid.UUID,
    course_id: uuid.UUID,
    current_user_id: uuid.UUID,
    db: Any,
    llm_client: Any | None = None,
    backoff_seconds: float = RETRY_BACKOFF_SECONDS,
) -> CurriculumAlignmentCheck:
    """Run (or honestly fail) one curriculum alignment check.

    Validation gates run before any text use or client acquisition. The
    typed ``run_alignment_check`` outcome drives persistence: a rejected or
    failed whole response stores a failed check atomically (no partial
    results), while a successful response is grounded against the evaluated
    pages only.
    """
    document = require_owned_document(document_id, current_user_id, db)
    validate_document_for_alignment(document)

    enforce_recheck_cooldown(
        document_id=document_id,
        course_id=course_id,
        current_user_id=current_user_id,
        db=db,
    )

    pages = load_document_pages(db, document_id)
    if not pages:
        raise NoUsableDocumentTextError(
            f"Document {document_id} has no usable persisted text; reprocess "
            "the SLM before running an alignment check."
        )

    course = get_course(course_id, db)
    if course is None:
        raise CourseNotFoundError(f"Course {course_id} not found")
    validate_course_program(course, document)

    mapped = get_mapped_objectives(course.course_id, db)
    if not mapped:
        raise NoCurriculumMapError(
            f"No curriculum map seeded for course {course.course_code}"
        )
    validate_objective_programs(mapped)

    evaluated_pages, coverage = select_pages_within_budget(
        pages, _MAX_SLM_TEXT_CHARS
    )
    if not evaluated_pages:
        raise NoUsableDocumentTextError(
            f"Document {document_id} cannot fit even one complete page within "
            "the alignment prompt budget, so it cannot be evaluated."
        )
    slm_text = "\n\n".join(page.text for page in evaluated_pages)

    client = llm_client or get_llm_client()
    outcome = run_alignment_check(
        client,
        [{"code": m["code"], "description": m["description"]} for m in mapped],
        slm_text,
        backoff_seconds=backoff_seconds,
    )

    if not outcome.success:
        result = build_failed_result(
            outcome=outcome,
            coverage=coverage,
            fallback_model=getattr(client, "model", None),
            total_mapped_objectives=len(mapped),
        )
        return persist_alignment_check(
            db=db,
            document_id=document_id,
            course_id=course.course_id,
            result=result,
        )

    result = build_successful_result(
        outcome=outcome,
        coverage=coverage,
        fallback_model=getattr(client, "model", None),
        mapped=mapped,
        evaluated_pages=evaluated_pages,
    )
    return persist_alignment_check(
        db=db,
        document_id=document_id,
        course_id=course.course_id,
        result=result,
    )


__all__ = [
    "run_curriculum_alignment_check",
]
