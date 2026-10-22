"""Validation and admission checks for curriculum alignment."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from math import ceil
from typing import Any

from server.core.config import get_settings
from server.modules.curriculum.models import Course
from server.modules.curriculum.service import normalize_program
from server.modules.documents.models import Document

from .exceptions import (
    AlignmentCheckCooldownError,
    CourseProgramMismatchError,
    CurriculumMapProgramError,
    DocumentAccessDeniedError,
    DocumentNotReadyError,
    DocumentProgramError,
    DocumentSourceTypeError,
)
from .models import CurriculumAlignmentCheck

#: Supported institutional programs; ``BSIT`` remains a BSInfoTech read alias.
SUPPORTED_PROGRAMS = frozenset({"BSCS", "BSInfoTech"})

SLM_SOURCE_TYPE = "slm"
PROCESSED_STATUS = "PROCESSED"

_LOG_CAT_COOLDOWN = "curriculum_alignment.cooldown.denied"

logger = logging.getLogger(__name__)


def require_owned_document(
    document_id: uuid.UUID, current_user_id: uuid.UUID, db: Any
) -> Document:
    """Return the document unless it is missing or owned by someone else.

    Curriculum-map documents are always SLMs in practice, so this mirrors only
    the owner-only branch of ``documents/access.py::_is_document_accessible``
    -- inlined rather than imported, since that helper is private to the
    documents module. Non-owners are masked as 404 so the endpoint never
    leaks whether the document exists.
    """
    document = db.get(Document, document_id)
    if document is None or document.uploaded_by != current_user_id:
        raise DocumentAccessDeniedError(f"Document {document_id} not found")
    return document


def validate_document_for_alignment(document: Document) -> None:
    """Require a processed SLM from a supported institutional program."""
    if document.source_type != SLM_SOURCE_TYPE:
        raise DocumentSourceTypeError(
            f"Document {document.document_id} has source_type "
            f"{document.source_type!r}; only 'slm' documents can be "
            "curriculum-alignment checked."
        )
    if document.processing_status != PROCESSED_STATUS:
        raise DocumentNotReadyError(
            f"Document {document.document_id} has not finished processing "
            f"(status {document.processing_status!r}); wait for ingestion to "
            "complete before running an alignment check."
        )
    if normalize_program(document.program) not in SUPPORTED_PROGRAMS:
        raise DocumentProgramError(
            f"Document {document.document_id} belongs to unsupported program "
            f"{document.program!r}; BSCS and BSInfoTech (legacy alias 'BSIT') "
            "are supported for curriculum alignment."
        )


def validate_course_program(course: Course, document: Document) -> None:
    """Enforce that the course program is supported and matches the document."""
    if normalize_program(course.program) not in SUPPORTED_PROGRAMS:
        raise CourseProgramMismatchError(
            f"Course {course.course_code} belongs to unsupported program "
            f"{course.program!r}; BSCS and BSInfoTech (legacy alias 'BSIT') "
            "are supported for curriculum alignment."
        )
    if normalize_program(course.program) != normalize_program(document.program):
        raise CourseProgramMismatchError(
            f"Course {course.course_code} program {course.program!r} does not "
            f"match the document program {document.program!r}."
        )


def validate_objective_programs(
    mapped: list[dict[str, Any]], course_program: str
) -> None:
    """Require every mapped objective to belong to the selected course program."""
    expected_program = normalize_program(course_program)
    for objective in mapped:
        objective_program = normalize_program(objective["program"])
        if (
            objective_program not in SUPPORTED_PROGRAMS
            or objective_program != expected_program
        ):
            raise CurriculumMapProgramError(
                f"Objective {objective['code']} program {objective['program']!r} "
                f"must match the supported course program {course_program!r}."
            )


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def enforce_recheck_cooldown(
    document_id: uuid.UUID,
    course_id: uuid.UUID,
    current_user_id: uuid.UUID,
    db: Any,
) -> None:
    settings = get_settings()
    cooldown_seconds = settings.curriculum_alignment_recheck_cooldown_seconds
    if cooldown_seconds <= 0:
        return

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

    logger.warning(
        "alignment cooldown active",
        extra={"category": _LOG_CAT_COOLDOWN},
    )
    raise AlignmentCheckCooldownError(
        "This document+course alignment check was already run recently",
        retry_after_seconds=retry_after,
    )


__all__ = [
    "SUPPORTED_PROGRAMS",
    "SLM_SOURCE_TYPE",
    "PROCESSED_STATUS",
    "require_owned_document",
    "validate_document_for_alignment",
    "validate_course_program",
    "validate_objective_programs",
    "enforce_recheck_cooldown",
]
