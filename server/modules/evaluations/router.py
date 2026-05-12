"""
Evaluations endpoints. Job submission, listing, details, and status polling with BackgroundTask support and 404-on-unauthorized.
"""
from __future__ import annotations
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from server.modules.auth.dependencies import require_authenticated_user
from server.modules.auth.service import AuthenticatedUser
from server.modules.evaluations.schemas import (
    EvaluationSubmitRequest, EvaluationResponse,
    EvaluationListResponse, EvaluationStatusResponse
)
from server.modules.evaluations.service import (
    create_evaluation, get_evaluation, list_evaluations, get_evaluation_status
)
from server.modules.evaluations.orchestrator import run_evaluation_job
from server.modules.documents.exceptions import DocumentNotFoundError
from server.modules.evaluations.exceptions import (
    EvaluationNotFoundError,
    EvaluationPipelineUnavailableError,
    InvalidEvaluationTargetError,
)

from server.core.database import get_db_session

router = APIRouter(prefix="/evaluations", tags=["evaluations"])

@router.post("/", response_model=EvaluationResponse, status_code=status.HTTP_202_ACCEPTED)
def submit_evaluation(
    background_tasks: BackgroundTasks,
    req: EvaluationSubmitRequest,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any = Depends(get_db_session),
) -> EvaluationResponse:
    try:
        response = create_evaluation(req, submitted_by=current_user.id, db=db)
        background_tasks.add_task(run_evaluation_job, response.evaluation_id)
        return response
    except DocumentNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    except InvalidEvaluationTargetError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except EvaluationPipelineUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

@router.get("/", response_model=EvaluationListResponse)
def list_evals(
    page: int = 1,
    page_size: int = 20,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any = Depends(get_db_session),
) -> EvaluationListResponse:
    return list_evaluations(page, page_size, current_user.id, current_user.role.value, db=db)

@router.get("/{evaluation_id}", response_model=EvaluationResponse)
def get_eval(
    evaluation_id: UUID,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any = Depends(get_db_session),
) -> EvaluationResponse:
    try:
        return get_evaluation(evaluation_id, current_user.id, current_user.role.value, db=db)
    except EvaluationNotFoundError:
        raise HTTPException(status_code=404, detail="Evaluation not found.")

@router.get("/{evaluation_id}/status", response_model=EvaluationStatusResponse)
def get_eval_status(
    evaluation_id: UUID,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any = Depends(get_db_session),
) -> EvaluationStatusResponse:
    try:
        return get_evaluation_status(evaluation_id, current_user.id, current_user.role.value, db=db)
    except EvaluationNotFoundError:
        raise HTTPException(status_code=404, detail="Evaluation not found.")

__all__ = ["router"]
