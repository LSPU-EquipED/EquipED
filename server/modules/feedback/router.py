"""Routes for the feedback module: criterion-level reviewer feedback."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from server.core.database import get_db_session
from server.modules.auth.dependencies import require_authenticated_user
from server.modules.auth.service import AuthenticatedUser
from server.modules.feedback.exceptions import (
    EvaluationNotFoundError,
    InvalidFeedbackTargetError,
)
from server.modules.feedback.schemas import (
    CriterionFeedbackCreate,
    CriterionFeedbackResponse,
)
from server.modules.feedback.service import create_criterion_feedback

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post(
    "/{evaluation_id}/criteria/{criterion_id}",
    response_model=CriterionFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_criterion_feedback(
    evaluation_id: uuid.UUID,
    criterion_id: str,
    body: CriterionFeedbackCreate,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db=Depends(get_db_session),
):
    try:
        log = create_criterion_feedback(
            db,
            evaluation_id=evaluation_id,
            criterion_id=criterion_id,
            agent_name=body.agent_name,
            action=body.action,
            user_id=current_user.id,
            user_role=current_user.role,
            score=body.score,
            justification=body.justification,
            notes=body.notes,
        )
    except EvaluationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except InvalidFeedbackTargetError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    return CriterionFeedbackResponse(
        log_id=log.log_id,
        evaluation_id=log.evaluation_id,
        user_id=log.user_id,
        agent_name=log.agent_name,
        criterion_id=log.criterion_id,
        action=log.action,
        edited_json=log.edited_json,
        notes=log.notes,
        created_at=log.created_at,
    )


__all__ = ["router"]
