"""Evaluation admission and target validation."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from server.modules.auth.models import UserRole
from server.modules.documents import persistence
from server.modules.documents.curriculum_readiness import check_curriculum_readiness
from server.modules.documents.exceptions import DocumentNotFoundError
from server.modules.documents.models import Document
from server.modules.documents.schemas import REFERENCE_SOURCE_TYPES
from server.modules.evaluations.exceptions import (
    EvaluationPipelineUnavailableError,
    InvalidEvaluationTargetError,
)
from server.modules.evaluations.models import (
    EvaluationJob,
    EvaluationStatus,
)
from server.modules.evaluations.schemas import (
    EvaluationResponse,
    EvaluationSubmitRequest,
)
from sqlalchemy import inspect

logger = logging.getLogger(__name__)


def _duration_seconds(
    submitted_at: datetime | None,
    completed_at: datetime | None,
) -> float | None:
    if completed_at is not None and submitted_at is not None:
        return (completed_at - submitted_at).total_seconds()
    return None


def create_evaluation(
    req: EvaluationSubmitRequest,
    submitted_by: uuid.UUID,
    db: Any = None,
    *,
    submitted_by_role: str | None = None,
    with_commit: bool = True,
) -> EvaluationResponse:
    if db is None:
        raise EvaluationPipelineUnavailableError(
            "Evaluation pipeline is not available yet."
        )

    # Validate SLM target (existence + source_type==slm + ownership) FIRST to
    # preserve security masking: missing, foreign SLM, or non-SLM returns
    # DocumentNotFoundError (404) before we reveal program or curriculum requirements.
    document = _validate_evaluation_target(
        req.document_id,
        submitted_by,
        db,
        expected_source_type="slm",
        user_role=submitted_by_role,
    )
    if not (req.confirmed_program and req.confirmed_program.strip()):
        raise InvalidEvaluationTargetError(
            "confirmed_program is required for evaluation submission."
        )

    confirmed_prog = req.confirmed_program.strip()
    if confirmed_prog not in ("BSCS", "BSInfoTech"):
        raise InvalidEvaluationTargetError(
            "Unsupported confirmed_program on write. Only BSCS and BSInfoTech "
            "are supported; BSIT is not accepted on submission."
        )
    if document.program is None:
        document.program = confirmed_prog

    target_agent = getattr(req, "target_agent", "sme") or "sme"
    if target_agent not in ("sme", "coordinator", "gad", "itso"):
        raise InvalidEvaluationTargetError(
            "Invalid target_agent. Must be one of sme, coordinator, gad, itso."
        )

    curriculum_id: uuid.UUID | None = None
    # Single-agent evaluations are 100% complete for the targeted domain.
    # The legacy partial mode is deprecated.
    partial_without_curriculum: bool = False
    partial_reason: str | None = None

    if target_agent == "coordinator":
        if req.curriculum_id is None:
            raise InvalidEvaluationTargetError(
                "Curriculum context is required for Program Coordinator evaluation."
            )
        readiness = check_curriculum_readiness(
            document=req.curriculum_id,
            program=confirmed_prog,
            db=db,
        )
        if not readiness.is_ready:
            logger.warning(
                "Curriculum readiness check failed during evaluation admission: "
                "curriculum_id=%s, program=%s, reason=%s",
                req.curriculum_id,
                confirmed_prog,
                readiness.reason,
            )
            raise InvalidEvaluationTargetError(
                "Curriculum is not ready for evaluation."
            )
        curriculum_id = readiness.document_id
    elif req.curriculum_id is not None:
        readiness = check_curriculum_readiness(
            document=req.curriculum_id,
            program=confirmed_prog,
            db=db,
        )
        if not readiness.is_ready:
            logger.warning(
                "Curriculum readiness check failed during evaluation admission: "
                "curriculum_id=%s, program=%s, reason=%s",
                req.curriculum_id,
                confirmed_prog,
                readiness.reason,
            )
            raise InvalidEvaluationTargetError(
                "Curriculum is not ready for evaluation."
            )
        curriculum_id = readiness.document_id

    syllabus = None
    if req.syllabus_id:
        syllabus = _validate_evaluation_target(
            req.syllabus_id,
            submitted_by,
            db,
            expected_source_type="syllabus",
        )

    job = EvaluationJob(
        evaluation_id=uuid.uuid4(),
        document_id=document.document_id,
        syllabus_id=syllabus.document_id if syllabus is not None else None,
        curriculum_id=curriculum_id,
        status=EvaluationStatus.SUBMITTED.value,
        error_message=None,
        target_agent=target_agent,
        partial_without_curriculum=partial_without_curriculum,
        partial_reason=partial_reason,
        confirmed_program=confirmed_prog,
        submitted_by=submitted_by,
        submitted_at=datetime.now(UTC),
        completed_at=None,
    )
    db.add(job)
    if with_commit:
        db.commit()

    return EvaluationResponse(
        evaluation_id=job.evaluation_id,
        document_id=job.document_id,
        syllabus_id=job.syllabus_id,
        curriculum_id=job.curriculum_id,
        status=EvaluationStatus(job.status),
        error_message=job.error_message,
        target_agent=job.target_agent,
        partial_without_curriculum=job.partial_without_curriculum,
        partial_reason=job.partial_reason,
        confirmed_program=job.confirmed_program,
        submitted_by=job.submitted_by,
        submitted_at=job.submitted_at,
        completed_at=job.completed_at,
        duration_seconds=_duration_seconds(job.submitted_at, job.completed_at),
    )


def _validate_evaluation_target(
    document_id: uuid.UUID,
    current_user_id: uuid.UUID,
    db: Any = None,
    *,
    expected_source_type: str,
    user_role: str | None = None,
) -> Document:
    if db is None:
        raise EvaluationPipelineUnavailableError(
            "Evaluation pipeline is not available yet."
        )

    document = db.get(Document, document_id)
    if document is None:
        raise DocumentNotFoundError(f"Document {document_id} not found")

    # Admins bypass the SLM ownership check so they can create
    # benchmark evaluations on faculty-uploaded SLM documents.
    is_admin = user_role == UserRole.ADMIN.value if user_role else False

    # For evaluation primary target (slm), combine existence, source_type == 'slm',
    # and ownership into the same masked DocumentNotFoundError (404).
    if expected_source_type == "slm":
        if document.source_type != "slm":
            raise DocumentNotFoundError(f"Document {document_id} not found")
        if not is_admin and document.uploaded_by != current_user_id:
            raise DocumentNotFoundError(f"Document {document_id} not found")
    else:
        # Non-SLM targets (e.g. syllabus)
        if not is_admin:
            if expected_source_type in REFERENCE_SOURCE_TYPES:
                # References are shared; skip ownership check
                pass
            elif document.uploaded_by != current_user_id:
                raise DocumentNotFoundError(f"Document {document_id} not found")

        if document.source_type != expected_source_type:
            raise InvalidEvaluationTargetError(
                f"Document must have source_type={expected_source_type}."
            )

    if document.processing_status != "PROCESSED":
        raise InvalidEvaluationTargetError(
            "Document must be fully processed before evaluation."
        )

    chunks = persistence.get_document_chunks(document_id, db=db)
    if not chunks:
        raise InvalidEvaluationTargetError(
            "Document must have chunks before evaluation submission."
        )

    if document.source_type != "slm" and not all(
        getattr(chunk, "chroma_stored", False) for chunk in chunks
    ):
        raise InvalidEvaluationTargetError(
            "Document must have Chroma-ready chunks before evaluation submission."
        )

    return document


def admission_schema_ready(db: Any) -> bool:
    """Verify the complete admission lease contract without mutating schema."""
    try:
        bind = db.get_bind()
        inspector = inspect(bind)
        columns = {c["name"] for c in inspector.get_columns("evaluation_jobs")}
        required_columns = {
            "admission_slot",
            "execution_token",
            "execution_started_at",
            "execution_heartbeat_at",
        }
        if not required_columns.issubset(columns):
            return False
        checks = {
            c.get("name") for c in inspector.get_check_constraints("evaluation_jobs")
        }
        uniques = {
            c.get("name") for c in inspector.get_unique_constraints("evaluation_jobs")
        }
        indexes = {i.get("name") for i in inspector.get_indexes("evaluation_jobs")}
        return (
            "ck_evaluation_admission_slot" in checks
            and "uq_evaluation_admission_slot" in uniques
            and "idx_jobs_admission_fifo" in indexes
        )
    except Exception:
        db.rollback()
        return False


__all__ = [
    "_validate_evaluation_target",
    "admission_schema_ready",
    "create_evaluation",
]
