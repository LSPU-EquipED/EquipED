"""Orchestration for the curriculum alignment check pipeline.

Fully independent of the SME/Coordinator/GAD/ITSO scoring pipeline and of
supervisor.py's parallel dispatch -- this is a separate, on-demand action
(design spec sections 2, 5, 9).
"""

from __future__ import annotations

import uuid
from typing import Any

from server.core.llm import get_llm_client

from .alignment_check import run_alignment_llm
from .comparison import compare_objective
from .document_text import extract_document_pages, find_evidence_page
from .exceptions import (
    AlignmentCheckNotFoundError,
    CourseNotFoundError,
    NoCurriculumMapError,
)
from .models import (
    Course,
    CurriculumAlignmentCheck,
    CurriculumMapCell,
    CurriculumObjective,
)

# Safety cap on the joined SLM text sent to the LLM. Mirrors the same
# budget-guard discipline as agents/base.py's prompt packing (design spec
# section 7: "SLM text exceeds prompt context budget"), just simpler since
# this pipeline sends one document's full text rather than ranked chunks.
_MAX_SLM_TEXT_CHARS = 20000


def _cap_slm_text(text: str) -> str:
    if len(text) <= _MAX_SLM_TEXT_CHARS:
        return text
    return text[:_MAX_SLM_TEXT_CHARS].rstrip() + "\n\n[...truncated for length...]"


def list_courses(db: Any) -> list[Course]:
    return db.query(Course).order_by(Course.course_code).all()


def _get_course(course_id: uuid.UUID, db: Any) -> Course:
    course = db.get(Course, course_id)
    if course is None:
        raise CourseNotFoundError(f"Course {course_id} not found")
    return course


def _get_mapped_objectives(course_id: uuid.UUID, db: Any) -> list[dict[str, Any]]:
    """Rows for this course only -- blank cells are absent rows, so this
    query already excludes them by construction (design spec section 3).
    """
    rows = (
        db.query(CurriculumMapCell, CurriculumObjective)
        .join(
            CurriculumObjective,
            CurriculumMapCell.objective_id == CurriculumObjective.objective_id,
        )
        .filter(CurriculumMapCell.course_id == course_id)
        .all()
    )
    return [
        {
            "code": objective.code,
            "description": objective.description,
            "expected_level": cell.level,
        }
        for cell, objective in rows
    ]


def run_curriculum_alignment_check(
    *,
    document_id: uuid.UUID,
    course_id: uuid.UUID,
    db: Any,
    llm_client: Any | None = None,
) -> CurriculumAlignmentCheck:
    course = _get_course(course_id, db)
    mapped = _get_mapped_objectives(course.course_id, db)
    if not mapped:
        raise NoCurriculumMapError(
            f"No curriculum map seeded for course {course.course_code}"
        )

    pages = extract_document_pages(document_id)
    slm_text = _cap_slm_text("\n\n".join(pages))

    client = llm_client or get_llm_client()
    llm_results = run_alignment_llm(
        client,
        [{"code": m["code"], "description": m["description"]} for m in mapped],
        slm_text,
    )
    llm_by_code = {r["objective_code"]: r for r in llm_results}

    objective_results: list[dict[str, Any]] = []
    status_counts = {
        "match": 0,
        "under_developed": 0,
        "over_developed": 0,
        "not_addressed": 0,
    }
    for objective in mapped:
        code = objective["code"]
        llm_result = llm_by_code.get(code)
        is_addressed = bool(llm_result and llm_result.get("is_addressed"))
        observed_level = llm_result.get("observed_level") if llm_result else None
        evidence = llm_result.get("evidence") if llm_result else None

        evidence_page = None
        if is_addressed and evidence:
            evidence_page = find_evidence_page(pages, evidence)
            if evidence_page is None:
                # Evidence not grounded in the source text -- downgrade
                # rather than trust an ungrounded claim (design spec s.7).
                is_addressed = False
                observed_level = None
                evidence = None

        status = compare_objective(
            is_addressed=is_addressed,
            observed_level=observed_level,
            expected_level=objective["expected_level"],
        )
        status_counts[status.replace("-", "_")] += 1

        objective_results.append(
            {
                "code": code,
                "description": objective["description"],
                "expected_level": objective["expected_level"],
                "is_addressed": is_addressed,
                "observed_level": observed_level,
                "status": status,
                "evidence": evidence,
                "evidence_page": evidence_page,
            }
        )

    check = CurriculumAlignmentCheck(
        document_id=document_id,
        course_id=course.course_id,
        model_name=getattr(client, "model", None),
        objective_results=objective_results,
        summary={"total_mapped_objectives": len(mapped), **status_counts},
        success=True,
    )
    db.add(check)
    db.commit()
    return check


def get_alignment_check(check_id: uuid.UUID, db: Any) -> CurriculumAlignmentCheck:
    check = db.get(CurriculumAlignmentCheck, check_id)
    if check is None:
        raise AlignmentCheckNotFoundError(f"Alignment check {check_id} not found")
    return check


def get_document_pages_for_check(check_id: uuid.UUID, db: Any) -> list[str]:
    check = get_alignment_check(check_id, db)
    return extract_document_pages(check.document_id)


__all__ = [
    "list_courses",
    "run_curriculum_alignment_check",
    "get_alignment_check",
    "get_document_pages_for_check",
]
