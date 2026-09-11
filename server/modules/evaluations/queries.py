"""Evaluation query operations and status read models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from server.modules.documents.models import Document
from server.modules.evaluations.agent_schedule import VALID_TARGET_AGENTS
from server.modules.evaluations.exceptions import (
    EvaluationNotFoundError,
    InvalidEvaluationTargetError,
)
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.evaluations.schemas import (
    EvaluationListItem,
    EvaluationListResponse,
    EvaluationResponse,
    EvaluationStatusResponse,
    LatestEvaluationItem,
    LatestEvaluationsResponse,
)
from sqlalchemy import func, select


def _duration_seconds(
    submitted_at: datetime | None,
    completed_at: datetime | None,
) -> float | None:
    if completed_at is not None and submitted_at is not None:
        return (completed_at - submitted_at).total_seconds()
    return None


def _check_ownership_or_404(
    row: EvaluationJob,
    current_user_id: uuid.UUID,
    current_user_role: str,
    evaluator_permissions: tuple[str, ...] | list[str] | None = None,
):
    if row.submitted_by != current_user_id:
        # Always mask existence as 404 if not the owner.
        raise EvaluationNotFoundError("Not found.")
    if current_user_role == "faculty" and evaluator_permissions:
        target = getattr(row, "target_agent", None) or "all"
        if target == "all":
            if not set(VALID_TARGET_AGENTS).issubset(set(evaluator_permissions)):
                raise EvaluationNotFoundError("Not found.")
        elif target not in evaluator_permissions:
            raise EvaluationNotFoundError("Not found.")


def get_evaluation(
    evaluation_id: uuid.UUID,
    current_user_id: uuid.UUID,
    current_user_role: str,
    db: Any = None,
    evaluator_permissions: tuple[str, ...] | list[str] | None = None,
) -> EvaluationResponse:
    row = db.get(EvaluationJob, evaluation_id) if db is not None else None
    if row is None:
        raise EvaluationNotFoundError(f"Evaluation {evaluation_id} not found")
    _check_ownership_or_404(
        row, current_user_id, current_user_role, evaluator_permissions
    )
    return EvaluationResponse(
        evaluation_id=row.evaluation_id,
        document_id=row.document_id,
        syllabus_id=row.syllabus_id,
        curriculum_id=row.curriculum_id,
        status=EvaluationStatus(row.status),
        error_message=row.error_message,
        target_agent=getattr(row, "target_agent", "all") or "all",
        partial_without_curriculum=row.partial_without_curriculum,
        partial_reason=row.partial_reason,
        confirmed_program=row.confirmed_program,
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
    target_agent: str | None = None,
    status: str | None = None,
    allowed_target_agents: tuple[str, ...] | list[str] | None = None,
) -> EvaluationListResponse:
    valid_targets = VALID_TARGET_AGENTS + ("all",)
    if target_agent is not None and target_agent not in valid_targets:
        raise InvalidEvaluationTargetError(
            f"Invalid target_agent '{target_agent}'. Must be one of {valid_targets}."
        )
    valid_statuses = tuple(s.value for s in EvaluationStatus)
    if status is not None and status not in valid_statuses:
        raise InvalidEvaluationTargetError(
            f"Invalid status '{status}'. Must be one of {valid_statuses}."
        )
    if db is not None:
        query = db.query(EvaluationJob)
        query = query.filter(EvaluationJob.submitted_by == current_user_id)
        if document_id is not None:
            query = query.filter(EvaluationJob.document_id == document_id)
        if target_agent is not None:
            query = query.filter(EvaluationJob.target_agent == target_agent)
        elif allowed_target_agents is not None:
            allowed = list(allowed_target_agents)
            if set(VALID_TARGET_AGENTS).issubset(set(allowed_target_agents)):
                allowed.append("all")
            query = query.filter(EvaluationJob.target_agent.in_(allowed))
        if status is not None:
            query = query.filter(EvaluationJob.status == status)
        total = query.count()
        rows = (
            query.order_by(EvaluationJob.submitted_at.desc())
            .offset((page - 1) * page_size)
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
                target_agent=getattr(row, "target_agent", "all") or "all",
                partial_without_curriculum=row.partial_without_curriculum,
                partial_reason=row.partial_reason,
                confirmed_program=row.confirmed_program,
                submitted_at=row.submitted_at,
                completed_at=row.completed_at,
                duration_seconds=_duration_seconds(row.submitted_at, row.completed_at),
            )
            for row in rows
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
    evaluator_permissions: tuple[str, ...] | list[str] | None = None,
) -> EvaluationStatusResponse:
    row = db.get(EvaluationJob, evaluation_id) if db is not None else None
    if row is None:
        raise EvaluationNotFoundError(f"Evaluation {evaluation_id} not found")
    _check_ownership_or_404(
        row, current_user_id, current_user_role, evaluator_permissions
    )
    return EvaluationStatusResponse(
        evaluation_id=row.evaluation_id,
        status=EvaluationStatus(row.status),
        error_message=row.error_message,
        target_agent=getattr(row, "target_agent", "all") or "all",
        partial_without_curriculum=row.partial_without_curriculum,
        partial_reason=row.partial_reason,
        completed_at=row.completed_at,
        duration_seconds=_duration_seconds(row.submitted_at, row.completed_at),
    )


def get_latest_evaluations(
    document_ids: list[uuid.UUID],
    current_user_id: uuid.UUID,
    db: Any = None,
    evaluator_permissions: tuple[str, ...] | list[str] | None = None,
    current_user_role: str = "faculty",
) -> LatestEvaluationsResponse:
    if not document_ids or db is None:
        return LatestEvaluationsResponse(items=[])

    rn_col = (
        func.row_number()
        .over(
            partition_by=EvaluationJob.document_id,
            order_by=(
                EvaluationJob.submitted_at.desc(),
                EvaluationJob.evaluation_id.desc(),
            ),
        )
        .label("rn")
    )

    predicates = [
        EvaluationJob.submitted_by == current_user_id,
        EvaluationJob.document_id.in_(document_ids),
    ]
    if current_user_role == "faculty" and evaluator_permissions:
        allowed = list(evaluator_permissions)
        if set(VALID_TARGET_AGENTS).issubset(set(evaluator_permissions)):
            allowed.append("all")
        predicates.append(EvaluationJob.target_agent.in_(allowed))

    subquery = (
        select(
            EvaluationJob.document_id,
            EvaluationJob.evaluation_id,
            EvaluationJob.status,
            EvaluationJob.target_agent,
            EvaluationJob.submitted_at,
            EvaluationJob.completed_at,
            EvaluationJob.error_message,
            rn_col,
        )
        .where(*predicates)
        .subquery()
    )

    stmt = select(
        subquery.c.document_id,
        subquery.c.evaluation_id,
        subquery.c.status,
        subquery.c.target_agent,
        subquery.c.submitted_at,
        subquery.c.completed_at,
        subquery.c.error_message,
    ).where(subquery.c.rn == 1)

    rows = db.execute(stmt).all()

    items = [
        LatestEvaluationItem(
            document_id=row.document_id,
            evaluation_id=row.evaluation_id,
            status=EvaluationStatus(row.status),
            target_agent=row.target_agent,
            submitted_at=row.submitted_at,
            completed_at=row.completed_at,
            error_message=row.error_message,
        )
        for row in rows
    ]
    return LatestEvaluationsResponse(items=items)


__all__ = [
    "_check_ownership_or_404",
    "get_evaluation",
    "get_evaluation_status",
    "get_latest_evaluations",
    "list_evaluations",
]
