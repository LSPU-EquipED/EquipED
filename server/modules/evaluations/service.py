"""
Evaluations business logic layer. Enforces job lifecycle, role/ownership, and status transitions (including helpers for orchestrator use). Unauthorized access is always 404 (masked) for non-owners.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from server.modules.documents.exceptions import DocumentNotFoundError
from server.modules.documents.models import Document
from server.modules.documents.service import get_document_chunks
from server.modules.evaluations.exceptions import (
    EvaluationExecutionOwnershipError,
    EvaluationNotFoundError,
    EvaluationPipelineUnavailableError,
    InvalidEvaluationTargetError,
    InvalidStatusTransitionError,
)
from server.modules.evaluations.models import (
    EvaluationJob,
    EvaluationStatus,
    can_transition_status,
)
from server.modules.evaluations.schemas import (
    EvaluationListItem,
    EvaluationListResponse,
    EvaluationResponse,
    EvaluationStatusResponse,
    EvaluationSubmitRequest,
)
from sqlalchemy import update

logger = logging.getLogger(__name__)


# Statuses considered terminal — once entered, no further transitions
# or token claims are allowed.
_TERMINAL_STATUSES: tuple[str, ...] = (
    EvaluationStatus.COMPLETED.value,
    EvaluationStatus.FAILED.value,
)


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
        raise EvaluationPipelineUnavailableError("Evaluation pipeline is not available yet.")

    # Validate SLM ownership FIRST to preserve security masking:
    # a foreign SLM returns DocumentNotFoundError (404) before we
    # reveal any curriculum_id requirements.
    document = _validate_evaluation_target(
        req.document_id,
        submitted_by,
        db,
        expected_source_type="slm",
        user_role=submitted_by_role,
    )

    if req.curriculum_id is None and not req.partial_without_curriculum:
        raise InvalidEvaluationTargetError(
            "curriculum_id is required for evaluation submission "
            "unless partial_without_curriculum is explicitly True."
        )
    # When curriculum_id IS present, full evaluation semantics win
    # regardless of the partial flag.
    effective_partial = req.partial_without_curriculum and req.curriculum_id is None
    syllabus = None
    if req.syllabus_id:
        syllabus = _validate_evaluation_target(
            req.syllabus_id,
            submitted_by,
            db,
            expected_source_type="syllabus",
        )
    curriculum = None
    if req.curriculum_id:
        curriculum = _validate_evaluation_target(
            req.curriculum_id,
            submitted_by,
            db,
            expected_source_type="curriculum",
        )

    job = EvaluationJob(
        evaluation_id=uuid.uuid4(),
        document_id=document.document_id,
        syllabus_id=syllabus.document_id if syllabus is not None else None,
        curriculum_id=curriculum.document_id if curriculum is not None else None,
        status=EvaluationStatus.SUBMITTED.value,
        error_message=None,
        partial_without_curriculum=effective_partial,
        partial_reason=(
            "No curriculum reference was available; Coordinator review was skipped."
            if effective_partial
            else None
        ),
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
        partial_without_curriculum=job.partial_without_curriculum,
        partial_reason=job.partial_reason,
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
        raise EvaluationPipelineUnavailableError("Evaluation pipeline is not available yet.")

    from server.modules.auth.models import UserRole
    from server.modules.documents.schemas import REFERENCE_SOURCE_TYPES

    document = db.get(Document, document_id)
    if document is None:
        raise DocumentNotFoundError(f"Document {document_id} not found")

    # Admins bypass the SLM ownership check so they can create
    # benchmark evaluations on faculty-uploaded SLM documents.
    is_admin = user_role == UserRole.ADMIN.value if user_role else False
    if not is_admin:
        # SLM documents require strict ownership. Reference documents
        # (syllabus, curriculum) are shared to all authenticated users.
        if expected_source_type == "slm" and document.uploaded_by != current_user_id:
            raise DocumentNotFoundError(f"Document {document_id} not found")
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

    chunks = get_document_chunks(document_id, db=db)
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

def _check_ownership_or_404(row: EvaluationJob, current_user_id: uuid.UUID, current_user_role: str):
    if row.submitted_by != current_user_id:
        # Always mask existence as 404 if not the owner.
        raise EvaluationNotFoundError("Not found.")

def get_evaluation(
    evaluation_id: uuid.UUID,
    current_user_id: uuid.UUID,
    current_user_role: str,
    db: Any = None,
) -> EvaluationResponse:
    row = db.get(EvaluationJob, evaluation_id) if db is not None else None
    if row is None:
        raise EvaluationNotFoundError(f"Evaluation {evaluation_id} not found")
    _check_ownership_or_404(row, current_user_id, current_user_role)
    return EvaluationResponse(
        evaluation_id=row.evaluation_id,
        document_id=row.document_id,
        syllabus_id=row.syllabus_id,
        curriculum_id=row.curriculum_id,
        status=EvaluationStatus(row.status),
        error_message=row.error_message,
        partial_without_curriculum=row.partial_without_curriculum,
        partial_reason=row.partial_reason,
        submitted_by=row.submitted_by,
        submitted_at=row.submitted_at,
        completed_at=row.completed_at,
        duration_seconds=_duration_seconds(row.submitted_at, row.completed_at),
    )

def list_evaluations(
    page: int,
    page_size: int,
    current_user_id: uuid.UUID,
    current_user_role: str,
    db: Any = None,
    *,
    document_id: uuid.UUID | None = None,
) -> EvaluationListResponse:
    if db is not None:
        query = db.query(EvaluationJob)
        query = query.filter(EvaluationJob.submitted_by == current_user_id)
        if document_id is not None:
            query = query.filter(EvaluationJob.document_id == document_id)
        total = query.count()
        rows = (
            query.order_by(EvaluationJob.submitted_at.desc())
            .offset((page-1) * page_size)
            .limit(page_size)
            .all()
        )
        doc_ids = [row.document_id for row in rows]
        doc_titles = {
            d.document_id: d.title
            for d in db.query(Document).filter(Document.document_id.in_(doc_ids)).all()
        }
        items = [
            EvaluationListItem(
                evaluation_id=row.evaluation_id,
                document_id=row.document_id,
                document_title=doc_titles.get(row.document_id),
                syllabus_id=row.syllabus_id,
                curriculum_id=row.curriculum_id,
                status=EvaluationStatus(row.status),
                partial_without_curriculum=row.partial_without_curriculum,
                partial_reason=row.partial_reason,
                submitted_at=row.submitted_at,
                completed_at=row.completed_at,
                duration_seconds=_duration_seconds(row.submitted_at, row.completed_at),
            ) for row in rows
        ]
        return EvaluationListResponse(
            items=items, total=total, page=page, page_size=page_size
        )
    return EvaluationListResponse(items=[], total=0, page=page, page_size=page_size)

def get_evaluation_status(
    evaluation_id: uuid.UUID,
    current_user_id: uuid.UUID,
    current_user_role: str,
    db: Any = None,
) -> EvaluationStatusResponse:
    row = db.get(EvaluationJob, evaluation_id) if db is not None else None
    if row is None:
        raise EvaluationNotFoundError(f"Evaluation {evaluation_id} not found")
    _check_ownership_or_404(row, current_user_id, current_user_role)
    return EvaluationStatusResponse(
        evaluation_id=row.evaluation_id,
        status=EvaluationStatus(row.status),
        error_message=row.error_message,
        partial_without_curriculum=row.partial_without_curriculum,
        partial_reason=row.partial_reason,
        completed_at=row.completed_at,
        duration_seconds=_duration_seconds(row.submitted_at, row.completed_at),
    )


def transition_evaluation_status(
    evaluation_id: uuid.UUID,
    new_status: EvaluationStatus,
    db: Any,
    *,
    error_message: str | None = None,
    execution_token: uuid.UUID | None = None,
) -> EvaluationStatusResponse:
    row = db.get(EvaluationJob, evaluation_id) if db is not None else None
    if row is None:
        raise EvaluationNotFoundError(f"Evaluation {evaluation_id} not found")
    if row.status in [EvaluationStatus.COMPLETED, EvaluationStatus.FAILED]:
        # No transitions out of terminal state
        return EvaluationStatusResponse(
            evaluation_id=row.evaluation_id,
            status=EvaluationStatus(row.status),
            error_message=row.error_message,
            partial_without_curriculum=row.partial_without_curriculum,
            partial_reason=row.partial_reason,
            completed_at=row.completed_at,
            duration_seconds=_duration_seconds(row.submitted_at, row.completed_at),
        )
    # Same-state non-terminal transition: idempotent no-op. Validate
    # token ownership when one is supplied, but do NOT clear/replace
    # the token or alter timestamps/status.
    if row.status == new_status.value:
        if execution_token is not None and row.execution_token != execution_token:
            raise EvaluationExecutionOwnershipError(
                f"Execution token mismatch for evaluation {evaluation_id}"
            )
        return EvaluationStatusResponse(
            evaluation_id=row.evaluation_id,
            status=EvaluationStatus(row.status),
            error_message=row.error_message,
            partial_without_curriculum=row.partial_without_curriculum,
            partial_reason=row.partial_reason,
            completed_at=row.completed_at,
            duration_seconds=_duration_seconds(row.submitted_at, row.completed_at),
        )
    if not can_transition_status(row.status, new_status):
        raise InvalidStatusTransitionError(f"Cannot move {row.status} -> {new_status}")
    if execution_token is not None and row.execution_token != execution_token:
        # Token was provided but does not match the current row ownership.
        # This guards against stale runners mutating state they no longer own.
        raise EvaluationExecutionOwnershipError(
            f"Execution token mismatch for evaluation {evaluation_id}"
        )
    row.status = new_status.value
    if error_message:
        row.error_message = error_message
    if new_status in [EvaluationStatus.COMPLETED, EvaluationStatus.FAILED]:
        row.completed_at = datetime.now(UTC)
        # Terminal transitions always clear execution ownership so the
        # job can be re-claimed if the row is later reset by recovery.
        row.execution_token = None
        row.execution_started_at = None
        row.execution_heartbeat_at = None
    db.commit()
    return EvaluationStatusResponse(
        evaluation_id=row.evaluation_id,
        status=EvaluationStatus(row.status),
        error_message=row.error_message,
        partial_without_curriculum=row.partial_without_curriculum,
        partial_reason=row.partial_reason,
        completed_at=row.completed_at,
        duration_seconds=_duration_seconds(row.submitted_at, row.completed_at),
    )


def acquire_evaluation_execution(
    db: Any,
    evaluation_id: uuid.UUID,
    execution_token: uuid.UUID,
) -> bool:
    """Atomically claim an evaluation job for execution.

    Returns True if the caller now owns the job, False if the job is
    missing, already terminal, or already claimed by another runner.

    Uses a single conditional UPDATE so concurrent runners cannot both
    succeed (the rowcount is 1 for exactly one claim).
    """

    now = datetime.now(UTC)
    result = db.execute(
        update(EvaluationJob)
        .where(
            EvaluationJob.evaluation_id == evaluation_id,
            EvaluationJob.execution_token.is_(None),
            EvaluationJob.status.not_in(_TERMINAL_STATUSES),
        )
        .values(
            execution_token=execution_token,
            execution_started_at=now,
            execution_heartbeat_at=now,
        )
    )
    db.commit()
    return result.rowcount == 1


def heartbeat_evaluation_execution(
    db: Any,
    evaluation_id: uuid.UUID,
    execution_token: uuid.UUID,
) -> bool:
    """Refresh the heartbeat timestamp for an owned evaluation job.

    Returns True if the heartbeat was updated, False if the token no
    longer matches (the caller has lost ownership).
    """

    now = datetime.now(UTC)
    result = db.execute(
        update(EvaluationJob)
        .where(
            EvaluationJob.evaluation_id == evaluation_id,
            EvaluationJob.execution_token == execution_token,
        )
        .values(execution_heartbeat_at=now)
    )
    db.commit()
    return result.rowcount == 1


def release_evaluation_execution(
    db: Any,
    evaluation_id: uuid.UUID,
    execution_token: uuid.UUID,
) -> bool:
    """Clear execution ownership fields for an owned evaluation job.

    Returns True if the fields were cleared, False if the token no longer
    matches (the caller has lost ownership).
    """

    result = db.execute(
        update(EvaluationJob)
        .where(
            EvaluationJob.evaluation_id == evaluation_id,
            EvaluationJob.execution_token == execution_token,
        )
        .values(
            execution_token=None,
            execution_started_at=None,
            execution_heartbeat_at=None,
        )
    )
    db.commit()
    return result.rowcount == 1


__all__ = [
    "create_evaluation",
    "get_evaluation",
    "list_evaluations",
    "get_evaluation_status",
    "transition_evaluation_status",
    "acquire_evaluation_execution",
    "heartbeat_evaluation_execution",
    "release_evaluation_execution",
    "_validate_evaluation_target",
]
