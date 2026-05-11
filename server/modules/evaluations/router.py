"""
Evaluations endpoints. Job submission, listing, details, and status polling with BackgroundTask support and 404-on-unauthorized.
"""
from __future__ import annotations
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, BackgroundTasks, status, HTTPException
from server.core.database import get_session_factory
from server.modules.auth.dependencies import require_authenticated_user
from server.modules.auth.service import AuthenticatedUser
from server.modules.evaluations.schemas import (
    EvaluationSubmitRequest, EvaluationResponse,
    EvaluationListResponse, EvaluationStatusResponse
)
from server.modules.evaluations.service import (
    create_evaluation, get_evaluation, list_evaluations, get_evaluation_status
)
from server.modules.evaluations.exceptions import EvaluationNotFoundError
from server.modules.evaluations.orchestrator import run_evaluation_job

from server.core.database import get_db_session

router = APIRouter(prefix="/evaluations", tags=["evaluations"])

@router.post("/", response_model=EvaluationResponse, status_code=status.HTTP_201_CREATED)
def submit_evaluation(
    req: EvaluationSubmitRequest,
    background_tasks: BackgroundTasks,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any = Depends(get_db_session),
) -> EvaluationResponse:
    resp = create_evaluation(req, submitted_by=current_user.id, db=db)
    # Dispatch orchestration as background task (Phase 1; pass session factory, not session)
    background_tasks.add_task(
        run_evaluation_job,
        resp.evaluation_id,
        resp.document_id,
        get_session_factory,  # pass factory; orchestrator will obtain a fresh session when it runs
    )
    return resp

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
