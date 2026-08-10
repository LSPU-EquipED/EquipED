"""Feedback service for preference logging and querying."""

from __future__ import annotations

import uuid

from server.modules.evaluations.models import EvaluationJob
from sqlalchemy import desc
from sqlalchemy.orm import Session

from .exceptions import EvaluationNotFoundError
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
    score: int | None = None,
    justification: str | None = None,
    notes: str | None = None,
) -> PreferenceLog:
    """Persist one reviewer feedback action for one agent's criterion.

    Raises EvaluationNotFoundError if evaluation_id doesn't exist.
    """

    if db.get(EvaluationJob, evaluation_id) is None:
        raise EvaluationNotFoundError(f"Evaluation {evaluation_id} not found")

    edited_json = (
        {"score": score, "justification": justification}
        if action == "EDIT"
        else None
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
