"""Orchestration for the curriculum alignment check pipeline.

Fully independent of the SME/Coordinator/GAD/ITSO scoring pipeline and of
supervisor.py's parallel dispatch -- this is a separate, on-demand action
(design spec sections 2, 5, 9).

Phase 2B contract:
- Document text comes exclusively from persisted, OCR-aware ``DocumentChunk``
  rows -- never from reopening the raw PDF.
- A strict validation gate runs before any text use or client acquisition:
  owner (404), ``source_type == "slm"`` (422), ``PROCESSED`` status (409),
  usable persisted chunks (409), and BSInfoTech program agreement across
  document/course/mapped objectives (422). Policy/syllabus/curriculum text
  can never reach the LLM.
- The typed ``run_alignment_check`` outcome is consumed. A rejected or failed
  whole response persists atomically as a failed check (no partial results),
  and only safe dataclass provenance plus text-source/coverage/failure-
  classification metadata is persisted -- never document text, raw prompts,
  or IDs.
- The old arbitrary head+tail character window is replaced by complete-page
  selection; coverage records scope ``full``/``bounded`` and how many
  pages/chars were evaluated. Under a bounded scope a not-addressed finding
  reads as ``not_observed`` (not a whole-document ``not_addressed`` claim)
  while positive grounded I/E/D results are preserved.
"""

from __future__ import annotations

import dataclasses
import logging
import uuid
from datetime import UTC, datetime, timedelta
from math import ceil
from typing import Any

from server.core.config import get_settings
from server.core.llm import get_llm_client

from .alignment_check import AlignmentCheckOutcome, run_alignment_check
from .alignment_runtime import RETRY_BACKOFF_SECONDS
from .comparison import compare_objective
from .document_text import (
    DocumentPage,
    find_evidence_page,
    load_document_pages,
    select_pages_within_budget,
)
from .exceptions import (
    AlignmentCheckCooldownError,
    AlignmentCheckNotFoundError,
    CourseNotFoundError,
    CourseProgramMismatchError,
    CurriculumMapProgramError,
    DocumentAccessDeniedError,
    DocumentNotReadyError,
    DocumentProgramError,
    DocumentSourceTypeError,
    NoCurriculumMapError,
    NoUsableDocumentTextError,
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
# this pipeline sends one document's text rather than ranked chunks.
#
# 20000 was too large in practice: a worst-case course (all 12 objectives,
# ~2800 chars of JSON) plus the ~1550-char prompt template plus 20000 chars
# of SLM text plus the requested 1800-token completion pushed the total
# request past this model's per-request token ceiling on Groq (observed:
# HTTP 413 "Request too large" for llama-3.1-8b-instant). 6000 keeps the
# worst-case total prompt under ~2600 tokens even before the completion
# budget, with real margin instead of running at the ceiling.
_MAX_SLM_TEXT_CHARS = 6000

#: Canonical program for the curriculum map; ``BSIT`` is only a read alias.
_CANONICAL_PROGRAM = "BSInfoTech"
_PROGRAM_ALIASES = ("BSInfoTech", "BSIT")

_SLM_SOURCE_TYPE = "slm"
_PROCESSED_STATUS = "PROCESSED"

#: Failure classification labels persisted in provenance.
_FAILURE_NONE = "none"
_FAILURE_REJECTED = "rejected_response"
_FAILURE_CONFIG = "configuration"
_FAILURE_TRANSIENT = "transient"
_FAILURE_CALL = "call_failed"

#: Provenance ``error_kind`` values that represent a transient (retryable)
#: LLM call failure rather than a rejected response or a config error.
_TRANSIENT_KINDS = frozenset(
    {
        "timeout",
        "connection",
        *{f"http_{code}" for code in (408, 429, *range(500, 600))},
    }
)

_LOG_CAT_COOLDOWN = "curriculum_alignment.cooldown.denied"

_logger = logging.getLogger(__name__)

_REJECTED_RESPONSE_KINDS = frozenset({"response_schema", "response_coverage"})


def _normalize_program(program: str | None) -> str | None:
    """Map the legacy ``BSIT`` alias onto the canonical ``BSInfoTech``.

    Any other value (including None) is returned unchanged so callers can
    distinguish "unsupported" from "matches".
    """
    if program in _PROGRAM_ALIASES:
        return _CANONICAL_PROGRAM
    return program


def _empty_summary(total_mapped_objectives: int) -> dict[str, int]:
    return {
        "total_mapped_objectives": total_mapped_objectives,
        "match": 0,
        "under_developed": 0,
        "over_developed": 0,
        "not_addressed": 0,
        "not_observed": 0,
    }


def _require_owned_document(
    document_id: uuid.UUID, current_user_id: uuid.UUID, db: Any
) -> Any:
    """Return the document unless it is missing or owned by someone else.

    Curriculum-map documents are always SLMs in practice, so this mirrors only
    the owner-only branch of ``documents/service.py::_is_document_accessible``
    -- inlined rather than imported, since that helper is private to the
    documents module. Non-owners are masked as 404 so the endpoint never
    leaks whether the document exists.
    """
    from server.modules.documents.models import Document

    document = db.get(Document, document_id)
    if document is None or document.uploaded_by != current_user_id:
        raise DocumentAccessDeniedError(f"Document {document_id} not found")
    return document


def _validate_document_for_alignment(document: Any) -> None:
    """Enforce the SLM-only, PROCESSED, BSInfoTech document gate."""
    if document.source_type != _SLM_SOURCE_TYPE:
        raise DocumentSourceTypeError(
            f"Document {document.document_id} has source_type "
            f"{document.source_type!r}; only 'slm' documents can be "
            "curriculum-alignment checked."
        )
    if document.processing_status != _PROCESSED_STATUS:
        raise DocumentNotReadyError(
            f"Document {document.document_id} has not finished processing "
            f"(status {document.processing_status!r}); wait for ingestion to "
            "complete before running an alignment check."
        )
    if _normalize_program(document.program) != _CANONICAL_PROGRAM:
        raise DocumentProgramError(
            f"Document {document.document_id} belongs to unsupported program "
            f"{document.program!r}; only {_CANONICAL_PROGRAM} (legacy alias "
            "'BSIT') is supported for curriculum alignment."
        )


def _validate_course_program(course: Course, document: Any) -> None:
    """Enforce that the course program is supported and matches the document."""
    if _normalize_program(course.program) != _CANONICAL_PROGRAM:
        raise CourseProgramMismatchError(
            f"Course {course.course_code} belongs to unsupported program "
            f"{course.program!r}; only {_CANONICAL_PROGRAM} (legacy alias "
            "'BSIT') is supported for curriculum alignment."
        )
    if _normalize_program(course.program) != _normalize_program(document.program):
        raise CourseProgramMismatchError(
            f"Course {course.course_code} program {course.program!r} does not "
            f"match the document program {document.program!r}."
        )


def _validate_objective_programs(mapped: list[dict[str, Any]]) -> None:
    """Enforce that every mapped objective belongs to the supported program."""
    for objective in mapped:
        if _normalize_program(objective["program"]) != _CANONICAL_PROGRAM:
            raise CurriculumMapProgramError(
                f"Objective {objective['code']} belongs to unsupported program "
                f"{objective['program']!r}; only {_CANONICAL_PROGRAM} (legacy "
                "alias 'BSIT') objectives can be alignment-checked."
            )


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _enforce_recheck_cooldown(
    document_id: uuid.UUID,
    course_id: uuid.UUID,
    current_user_id: uuid.UUID,
    db: Any,
) -> None:
    settings = get_settings()
    cooldown_seconds = settings.curriculum_alignment_recheck_cooldown_seconds
    if cooldown_seconds <= 0:
        return

    from server.modules.documents.models import Document

    last_check = (
        db.query(CurriculumAlignmentCheck)
        .join(Document, CurriculumAlignmentCheck.document_id == Document.document_id)
        .filter(
            CurriculumAlignmentCheck.document_id == document_id,
            CurriculumAlignmentCheck.course_id == course_id,
            Document.uploaded_by == current_user_id,
        )
        .order_by(CurriculumAlignmentCheck.run_at.desc())
        .first()
    )

    if last_check is None:
        return

    last_run_at = _to_utc(last_check.run_at)
    retry_delta_seconds = (
        last_run_at + timedelta(seconds=cooldown_seconds) - datetime.now(UTC)
    ).total_seconds()
    retry_after = int(ceil(retry_delta_seconds))
    if retry_after <= 0:
        return

    _logger.warning(
        "alignment cooldown active",
        extra={"category": _LOG_CAT_COOLDOWN},
    )
    raise AlignmentCheckCooldownError(
        "This document+course alignment check was already run recently",
        retry_after_seconds=retry_after,
    )


def _failure_classification(outcome: AlignmentCheckOutcome) -> str:
    """Safe, coarse failure classification persisted in provenance."""
    if outcome.success:
        return _FAILURE_NONE
    kind = outcome.provenance.error_kind if outcome.provenance else None
    if kind in _REJECTED_RESPONSE_KINDS:
        return _FAILURE_REJECTED
    if kind == "config":
        return _FAILURE_CONFIG
    if kind in _TRANSIENT_KINDS:
        return _FAILURE_TRANSIENT
    return _FAILURE_CALL


def _failure_message(outcome: AlignmentCheckOutcome) -> str:
    """Concise safe failure text distinguishing rejection, transient, and
    configuration failures -- never echoing provider payloads."""
    kind = outcome.provenance.error_kind if outcome.provenance else None
    if kind in _REJECTED_RESPONSE_KINDS:
        return (
            "The alignment check could not complete: the model returned a "
            "malformed or incomplete response that was rejected."
        )
    if kind == "config":
        return (
            "The alignment check could not complete: the LLM configuration "
            "is invalid (unsupported provider, missing model, or unusable "
            "timeout)."
        )
    if kind in _TRANSIENT_KINDS:
        return (
            "The alignment check could not complete: the LLM call failed "
            "transiently (timeout, rate limit, or service error) and no "
            "retry succeeded."
        )
    return (
        "The alignment check could not complete: the LLM call failed and no "
        "retry succeeded."
    )


def _persistable_provenance(
    outcome: AlignmentCheckOutcome,
    coverage: dict[str, Any],
) -> dict[str, Any]:
    """Safe provenance JSON for the existing JSON column.

    Dataclass provenance fields plus text-source and coverage metadata and a
    coarse failure classification. Never contains document text, raw prompts,
    or document/check IDs.
    """
    base = dataclasses.asdict(outcome.provenance) if outcome.provenance else {}
    return {
        **base,
        "text_source": {"source": "persisted_chunks", "ocr_aware": True},
        "coverage": coverage,
        "failure": _failure_classification(outcome),
    }


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
            "program": objective.program,
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
    backoff_seconds: float = RETRY_BACKOFF_SECONDS,
) -> CurriculumAlignmentCheck:
    """Run (or honestly fail) one curriculum alignment check.

    Validation gates run before any text use or client acquisition. The
    typed ``run_alignment_check`` outcome drives persistence: a rejected or
    failed whole response stores a failed check atomically (no partial
    results), while a successful response is grounded against the evaluated
    pages only.
    """
    document = _require_owned_document(document_id, current_user_id, db)
    _validate_document_for_alignment(document)

    _enforce_recheck_cooldown(
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

    course = _get_course(course_id, db)
    _validate_course_program(course, document)

    mapped = _get_mapped_objectives(course.course_id, db)
    if not mapped:
        raise NoCurriculumMapError(
            f"No curriculum map seeded for course {course.course_code}"
        )
    _validate_objective_programs(mapped)

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
        check = CurriculumAlignmentCheck(
            document_id=document_id,
            course_id=course.course_id,
            model_name=(
                outcome.provenance.model
                if outcome.provenance
                else getattr(client, "model", None)
            ),
            objective_results=[],
            summary=_empty_summary(len(mapped)),
            success=False,
            error_message=_failure_message(outcome),
            provenance=_persistable_provenance(outcome, coverage),
        )
        db.add(check)
        db.commit()
        return check

    scope_bounded = coverage["scope"] == "bounded"
    llm_by_code = {item.objective_code: item for item in outcome.results}

    objective_results: list[dict[str, Any]] = []
    status_counts = {
        "match": 0,
        "under_developed": 0,
        "over_developed": 0,
        "not_addressed": 0,
        "not_observed": 0,
    }
    for objective in mapped:
        code = objective["code"]
        llm_result = llm_by_code.get(code)
        is_addressed = bool(llm_result and llm_result.is_addressed)
        observed_level = llm_result.observed_level if llm_result else None
        evidence = llm_result.evidence if llm_result else None

        evidence_page = None
        if is_addressed and evidence:
            evidence_page = find_evidence_page(evaluated_pages, evidence)
            if evidence_page is None:
                # Evidence not grounded in the evaluated pages -- downgrade
                # rather than trust an ungrounded claim (design spec s.7).
                is_addressed = False
                observed_level = None
                evidence = None

        status = compare_objective(
            is_addressed=is_addressed,
            observed_level=observed_level,
            expected_level=objective["expected_level"],
        )
        if scope_bounded and status == "not_addressed":
            # Bounded scope: absence in the evaluated pages is "not observed",
            # never a whole-document "not addressed" claim.
            status = "not_observed"
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
        model_name=(
            outcome.provenance.model
            if outcome.provenance
            else getattr(client, "model", None)
        ),
        objective_results=objective_results,
        summary={"total_mapped_objectives": len(mapped), **status_counts},
        success=True,
        provenance=_persistable_provenance(outcome, coverage),
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


def delete_alignment_check(
    check_id: uuid.UUID, current_user_id: uuid.UUID, db: Any
) -> None:
    """Delete one check. Ownership-checked the same way get_alignment_check
    is: the check must exist and its document must belong to the caller.
    """
    check = db.get(CurriculumAlignmentCheck, check_id)
    if check is None:
        raise AlignmentCheckNotFoundError(f"Alignment check {check_id} not found")
    _require_owned_document(check.document_id, current_user_id, db)
    db.delete(check)
    db.commit()


__all__ = [
    "list_courses",
    "list_alignment_checks",
    "run_curriculum_alignment_check",
    "get_alignment_check",
    "get_document_pages_for_check",
    "get_coverage_metadata",
    "delete_alignment_check",
]
