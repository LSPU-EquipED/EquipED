"""
Evaluations business logic layer. Job lifecycle orchestration, role-based scoping enforced.
"""

from __future__ import annotations
import uuid
from datetime import UTC, datetime
from typing import Any

from server.modules.evaluations.models import EvaluationJob, EvaluationStatus, can_transition_status
from server.modules.evaluations.schemas import (
    EvaluationSubmitRequest, EvaluationResponse, EvaluationListItem,
    EvaluationListResponse, EvaluationStatusResponse,
)
from server.modules.evaluations.exceptions import (
    EvaluationNotFoundError, ForbiddenEvaluationAccessError, InvalidStatusTransitionError
)

def create_evaluation(
    req: EvaluationSubmitRequest,
    submitted_by: uuid.UUID,
    db: Any = None
) -> EvaluationResponse:
    """Create and submit an evaluation job for a document."""
    evaluation_id = uuid.uuid4()
    submitted_at = datetime.now(UTC)
    job = EvaluationJob(
        evaluation_id=evaluation_id,
        document_id=req.document_id,
        status=EvaluationStatus.SUBMITTED,
        error_message=None,
        submitted_by=submitted_by,
        submitted_at=submitted_at,
        completed_at=None,
    )
    if db is not None:
        db.add(job)
        db.commit()
    return EvaluationResponse(
        evaluation_id=evaluation_id,
        document_id=req.document_id,
        status=EvaluationStatus.SUBMITTED,
        error_message=None,
        submitted_by=submitted_by,
        submitted_at=submitted_at,
        completed_at=None,
    )

def get_evaluation(
    evaluation_id: uuid.UUID,
    current_user_id: uuid.UUID,
    current_user_role: str,
    db: Any = None,
) -> EvaluationResponse:
    """Return job details if visible to the user (role/ownership aware)."""
    row = db.get(EvaluationJob, evaluation_id) if db is not None else None
    if row is None:
        raise EvaluationNotFoundError(f"Evaluation {evaluation_id} not found")
    if current_user_role != "admin" and row.submitted_by != current_user_id:
        raise ForbiddenEvaluationAccessError()
    return EvaluationResponse(
        evaluation_id=row.evaluation_id,
        document_id=row.document_id,
        status=row.status,
        error_message=row.error_message,
        submitted_by=row.submitted_by,
        submitted_at=row.submitted_at,
        completed_at=row.completed_at,
    )

def list_evaluations(
    page: int,
    page_size: int,
    current_user_id: uuid.UUID,
    current_user_role: str,
    db: Any = None,
) -> EvaluationListResponse:
    """List jobs (admins see all, faculty see only theirs)."""
    if db is not None:
        query = db.query(EvaluationJob)
        if current_user_role != "admin":
            query = query.filter(EvaluationJob.submitted_by == current_user_id)
        total = query.count()
        rows = (
            query.order_by(EvaluationJob.submitted_at.desc())
            .offset((page-1) * page_size)
            .limit(page_size)
            .all()
        )
        items = [
            EvaluationListItem(
                evaluation_id=row.evaluation_id,
                document_id=row.document_id,
                status=row.status,
                submitted_at=row.submitted_at,
                completed_at=row.completed_at,
            ) for row in rows
        ]
        return EvaluationListResponse(
            items=items, total=total, page=page, page_size=page_size
        )
    # For in-memory, not needed yet
    return EvaluationListResponse(items=[], total=0, page=page, page_size=page_size)

def update_evaluation_status(
    evaluation_id: uuid.UUID,
    new_status: EvaluationStatus,
    current_user_id: uuid.UUID,
    current_user_role: str,
    db: Any = None,
) -> EvaluationStatusResponse:
    """Transition a job's status (supervisor/agent only)."""
    row = db.get(EvaluationJob, evaluation_id) if db is not None else None
    if row is None:
        raise EvaluationNotFoundError(f"Evaluation {evaluation_id} not found")
    if current_user_role != "admin" and row.submitted_by != current_user_id:
        raise ForbiddenEvaluationAccessError()
    if not can_transition_status(row.status, new_status):
        raise InvalidStatusTransitionError(f"Cannot move {row.status} -> {new_status}")
    row.status = new_status
    if new_status in (EvaluationStatus.COMPLETED, EvaluationStatus.FAILED):
        row.completed_at = datetime.now(UTC)
    db.commit()
    return EvaluationStatusResponse(
        evaluation_id=row.evaluation_id,
        status=row.status,
        error_message=row.error_message,
        completed_at=row.completed_at,
    )

__all__ = [
    "create_evaluation",
    "get_evaluation",
    "list_evaluations",
    "update_evaluation_status",
]
