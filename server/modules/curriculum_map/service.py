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
    DocumentAccessDeniedError,
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
#
# 20000 was too large in practice: a worst-case course (all 12 objectives,
# ~2800 chars of JSON) plus the ~1550-char prompt template plus 20000 chars
# of SLM text plus the requested 1800-token completion pushed the total
# request past this model's per-request token ceiling on Groq (observed:
# HTTP 413 "Request too large" for llama-3.1-8b-instant). 6000 keeps the
# worst-case total prompt under ~2600 tokens even before the completion
# budget, with real margin instead of running at the ceiling.
_MAX_SLM_TEXT_CHARS = 6000
_HEAD_TAIL_MARKER = "\n\n[...middle of document omitted...]\n\n"
_HALF_BUDGET = (_MAX_SLM_TEXT_CHARS - len(_HEAD_TAIL_MARKER)) // 2


def _cap_slm_text(text: str) -> str:
    """Cap SLM text to the prompt budget via a head+tail window sample.

    Real assessment content (the material that distinguishes "D" depth
    from "E") tends to sit at the END of SLM PDFs, under a "Performance
    Task(s)" section, not the start -- so a hard head-truncation
    systematically hides exactly the evidence needed to detect
    Demonstrative-level work. Keep roughly the first half of the budget
    (objectives/intro) and the last half (assessments/performance tasks)
    instead of just the head.
    """
    if len(text) <= _MAX_SLM_TEXT_CHARS:
        return text
    head = text[:_HALF_BUDGET].rstrip()
    tail = text[-_HALF_BUDGET:].lstrip()
    return head + _HEAD_TAIL_MARKER + tail


def _empty_summary(total_mapped_objectives: int) -> dict[str, int]:
    return {
        "total_mapped_objectives": total_mapped_objectives,
        "match": 0,
        "under_developed": 0,
        "over_developed": 0,
        "not_addressed": 0,
    }


def _require_owned_document(
    document_id: uuid.UUID, current_user_id: uuid.UUID, db: Any
) -> None:
    """Raise DocumentAccessDeniedError unless the document exists and is
    owned by ``current_user_id``.

    Curriculum-map documents are always SLMs (or other non-reference,
    non-policy types) in practice, so this mirrors only the owner-only
    branch of ``documents/service.py::_is_document_accessible`` -- inlined
    rather than imported, since that helper is private to the documents
    module.
    """
    from server.modules.documents.models import Document

    document = db.get(Document, document_id)
    if document is None or document.uploaded_by != current_user_id:
        raise DocumentAccessDeniedError(f"Document {document_id} not found")


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
    current_user_id: uuid.UUID,
    db: Any,
    llm_client: Any | None = None,
) -> CurriculumAlignmentCheck:
    _require_owned_document(document_id, current_user_id, db)
    course = _get_course(course_id, db)
    mapped = _get_mapped_objectives(course.course_id, db)
    if not mapped:
        raise NoCurriculumMapError(
            f"No curriculum map seeded for course {course.course_code}"
        )

    pages = extract_document_pages(document_id)
    if not pages:
        check = CurriculumAlignmentCheck(
            document_id=document_id,
            course_id=course.course_id,
            model_name=None,
            objective_results=[],
            summary=_empty_summary(len(mapped)),
            success=False,
            error_message="Could not extract text from the SLM PDF.",
        )
        db.add(check)
        db.commit()
        return check

    slm_text = _cap_slm_text("\n\n".join(pages))

    client = llm_client or get_llm_client()
    llm_results = run_alignment_llm(
        client,
        [{"code": m["code"], "description": m["description"]} for m in mapped],
        slm_text,
    )
    if not llm_results:
        check = CurriculumAlignmentCheck(
            document_id=document_id,
            course_id=course.course_id,
            model_name=getattr(client, "model", None),
            objective_results=[],
            summary=_empty_summary(len(mapped)),
            success=False,
            error_message=(
                "The alignment check could not complete (LLM error or "
                "invalid response)."
            ),
        )
        db.add(check)
        db.commit()
        return check

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


def get_alignment_check(
    check_id: uuid.UUID, current_user_id: uuid.UUID, db: Any
) -> CurriculumAlignmentCheck:
    check = db.get(CurriculumAlignmentCheck, check_id)
    if check is None:
        raise AlignmentCheckNotFoundError(f"Alignment check {check_id} not found")
    _require_owned_document(check.document_id, current_user_id, db)
    return check


def get_document_pages_for_check(
    check_id: uuid.UUID, current_user_id: uuid.UUID, db: Any
) -> list[str]:
    check = get_alignment_check(check_id, current_user_id, db)
    return extract_document_pages(check.document_id)


__all__ = [
    "list_courses",
    "run_curriculum_alignment_check",
    "get_alignment_check",
    "get_document_pages_for_check",
]
