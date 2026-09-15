"""Feedback service for preference logging and querying."""

from __future__ import annotations

import uuid

from server.modules.evaluations.models import EvaluationJob
from server.modules.synthesis.models import AgentResult, CriterionScore
from sqlalchemy import desc
from sqlalchemy.orm import Session

from .exceptions import EvaluationNotFoundError, InvalidFeedbackTargetError
from .models import PreferenceLog


def list_preference_logs(
    db: Session,
    action: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[PreferenceLog], int]:
    """Return paginated preference logs, optionally filtered by action."""

    query = db.query(PreferenceLog)
    if action:
        query = query.filter(PreferenceLog.action == action.upper())
    total = query.count()
    items = (
        query.order_by(desc(PreferenceLog.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def create_criterion_feedback(
    db: Session,
    *,
    evaluation_id: uuid.UUID,
    criterion_id: str,
    agent_name: str,
    action: str,
    user_id: uuid.UUID,
    user_role: str,
    score: int | None = None,
    justification: str | None = None,
    notes: str | None = None,
) -> PreferenceLog:
    """Persist one reviewer feedback action for one agent's criterion.

    Admins may give feedback on any evaluation. Faculty may only give
    feedback on evaluations they themselves submitted (self-review by the
    document's own author is out of scope for the DPO training-data use
    case, and would bias corrections toward whatever makes the submitter's
    own material look better).

    Raises EvaluationNotFoundError if evaluation_id doesn't exist OR if
    the caller is faculty and does not own it -- ownership failures are
    masked as "not found" rather than 403, matching the rest of the app's
    ownership-scoped endpoints (e.g. evaluations.service._check_ownership_or_404),
    so a faculty user can't use this endpoint to probe which evaluation
    IDs exist.
    """

    job = db.get(EvaluationJob, evaluation_id)
    if job is None:
        raise EvaluationNotFoundError(f"Evaluation {evaluation_id} not found")
    if user_role != "admin" and job.submitted_by != user_id:
        raise EvaluationNotFoundError(f"Evaluation {evaluation_id} not found")

    target_scores = (
        db.query(CriterionScore)
        .join(
            AgentResult,
            CriterionScore.agent_result_id == AgentResult.agent_result_id,
        )
        .filter(
            CriterionScore.evaluation_id == evaluation_id,
            CriterionScore.document_id == job.document_id,
            CriterionScore.criterion_id == criterion_id,
            AgentResult.evaluation_id == evaluation_id,
            AgentResult.agent_name == agent_name,
            AgentResult.document_id == job.document_id,
        )
        .all()
    )
    if len(target_scores) != 1:
        raise InvalidFeedbackTargetError(
            f"No unique criterion score found for evaluation {evaluation_id}, "
            f"agent '{agent_name}', criterion '{criterion_id}'"
        )

    edited_json = (
        {"score": score, "justification": justification} if action == "EDIT" else None
    )

    log = PreferenceLog(
        evaluation_id=evaluation_id,
        user_id=user_id,
        agent_name=agent_name,
        criterion_id=criterion_id,
        action=action,
        edited_json=edited_json,
        notes=notes,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
