"""
Evaluations endpoints. Implements job submission, listing, details, and status update (role-aware).
"""
from __future__ import annotations
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, status, HTTPException
from server.modules.evaluations.schemas import (
    EvaluationSubmitRequest, EvaluationResponse,
    EvaluationListResponse, EvaluationStatusResponse
)
from server.modules.evaluations.service import (
    create_evaluation, get_evaluation, list_evaluations, update_evaluation_status
)
from server.modules.evaluations.exceptions import (
    EvaluationNotFoundError, ForbiddenEvaluationAccessError, InvalidStatusTransitionError
)

# Dependency placeholders
# In deployed app, these should be injected via actual auth/session/user providers

def get_current_user_id() -> UUID:
    # TODO: Replace with real auth provider
    raise NotImplementedError("Auth context missing. Inject user id here.")

def get_current_user_role() -> str:
    # TODO: Replace with real auth provider
    raise NotImplementedError("Auth context missing. Inject user role here.")

router = APIRouter(prefix="/evaluations", tags=["evaluations"])

@router.post("/", response_model=EvaluationResponse, status_code=status.HTTP_201_CREATED)
def submit_evaluation(
    req: EvaluationSubmitRequest,
    current_user_id: UUID = Depends(get_current_user_id),
    db: Any = None,  # Replace with session
) -> EvaluationResponse:
    return create_evaluation(req, submitted_by=current_user_id, db=db)

@router.get("/", response_model=EvaluationListResponse)
def list_evals(
    page: int = 1,
    page_size: int = 20,
    current_user_id: UUID = Depends(get_current_user_id),
    current_user_role: str = Depends(get_current_user_role),
    db: Any = None,
) -> EvaluationListResponse:
    return list_evaluations(page, page_size, current_user_id, current_user_role, db=db)

@router.get("/{evaluation_id}", response_model=EvaluationResponse)
def get_eval(
    evaluation_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    current_user_role: str = Depends(get_current_user_role),
    db: Any = None,
) -> EvaluationResponse:
    try:
        return get_evaluation(evaluation_id, current_user_id, current_user_role, db=db)
    except EvaluationNotFoundError:
        raise HTTPException(status_code=404, detail="Evaluation not found.")
    except ForbiddenEvaluationAccessError:
        raise HTTPException(status_code=403, detail="Not authorized for this evaluation.")

@router.post("/{evaluation_id}/status", response_model=EvaluationStatusResponse)
def update_status(
    evaluation_id: UUID,
    new_status: str,
    current_user_id: UUID = Depends(get_current_user_id),
    current_user_role: str = Depends(get_current_user_role),
    db: Any = None,
) -> EvaluationStatusResponse:
    try:
        return update_evaluation_status(evaluation_id, new_status, current_user_id, current_user_role, db=db)
    except EvaluationNotFoundError:
        raise HTTPException(status_code=404, detail="Evaluation not found.")
    except ForbiddenEvaluationAccessError:
        raise HTTPException(status_code=403, detail="Not authorized for this evaluation.")
    except InvalidStatusTransitionError as err:
        raise HTTPException(status_code=400, detail=str(err))

__all__ = ["router"]
