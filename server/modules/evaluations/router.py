"""
Evaluations endpoints. Job submission, listing, details, and status polling with BackgroundTask support and 404-on-unauthorized.
"""
# ruff: noqa: E501

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from server.core.database import get_db_session
from server.core.exceptions import InfrastructureUnavailableError
from server.core.llm import probe_local_model_readiness
from server.modules.auth.dependencies import require_authenticated_user
from server.modules.auth.service import AuthenticatedUser
from server.modules.documents.exceptions import DocumentNotFoundError
from server.modules.evaluations.exceptions import (
    EvaluationNotFoundError,
    EvaluationPipelineUnavailableError,
    InvalidEvaluationTargetError,
)
from server.modules.evaluations.orchestrator import drain_evaluation_queue
from server.modules.evaluations.schemas import (
    EvaluationListResponse,
    EvaluationResponse,
    EvaluationStatusResponse,
    EvaluationSubmitRequest,
    LatestEvaluationsResponse,
)
from server.modules.evaluations.service import (
    admission_schema_ready,
    create_evaluation,
    get_evaluation,
    get_evaluation_status,
    get_latest_evaluations,
    list_evaluations,
)

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


@router.post(
    "/", response_model=EvaluationResponse, status_code=status.HTTP_202_ACCEPTED
)
def submit_evaluation(
    background_tasks: BackgroundTasks,
    req: EvaluationSubmitRequest,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any = Depends(get_db_session),
) -> EvaluationResponse:
    try:
        probe_local_model_readiness()
        if not admission_schema_ready(db):
            raise EvaluationPipelineUnavailableError(
                "Evaluation admission is unavailable"
            )
        response = create_evaluation(req, submitted_by=current_user.id, db=db)
        background_tasks.add_task(drain_evaluation_queue)
        return response
    except InfrastructureUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Local model readiness is unavailable.",
        )
    except DocumentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found."
        )
    except InvalidEvaluationTargetError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    except EvaluationPipelineUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )


@router.get("/", response_model=EvaluationListResponse)
def list_evals(
    page: int = 1,
    page_size: int = 20,
    document_id: UUID | None = None,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any = Depends(get_db_session),
) -> EvaluationListResponse:
    return list_evaluations(
        page,
        page_size,
        current_user.id,
        current_user.role.value,
        db=db,
        document_id=document_id,
    )


@router.get("/latest", response_model=LatestEvaluationsResponse)
def get_latest_evals(
    document_id: list[UUID] = Query(default=[]),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any = Depends(get_db_session),
) -> LatestEvaluationsResponse:
    deduped_ids = list(dict.fromkeys(document_id))
    if len(deduped_ids) > 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Maximum of 100 document IDs allowed.",
        )
    return get_latest_evaluations(
        deduped_ids,
        current_user.id,
        db=db,
    )


@router.get("/{evaluation_id}", response_model=EvaluationResponse)
def get_eval(
    evaluation_id: UUID,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any = Depends(get_db_session),
) -> EvaluationResponse:
    try:
        return get_evaluation(
            evaluation_id, current_user.id, current_user.role.value, db=db
        )
    except EvaluationNotFoundError:
        raise HTTPException(status_code=404, detail="Evaluation not found.")


@router.get("/{evaluation_id}/status", response_model=EvaluationStatusResponse)
def get_eval_status(
    evaluation_id: UUID,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any = Depends(get_db_session),
) -> EvaluationStatusResponse:
    try:
        return get_evaluation_status(
            evaluation_id, current_user.id, current_user.role.value, db=db
        )
    except EvaluationNotFoundError:
        raise HTTPException(status_code=404, detail="Evaluation not found.")


__all__ = ["router"]
