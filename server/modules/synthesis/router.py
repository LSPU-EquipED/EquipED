"""Routers for synthesis results and monitoring matrix views."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from server.core.database import get_db_session
from server.modules.auth.dependencies import require_admin, require_authenticated_user
from server.modules.synthesis.exceptions import (
    EvaluationResultIntegrityError,
    EvaluationResultsNotFoundError,
    UnsupportedProgramFilterError,
)
from server.modules.synthesis.schemas import (
    EvaluationResultsResponse,
    MatrixListResponse,
)
from server.modules.synthesis.service import (
    get_evaluation_results as service_get_evaluation_results,
)
from server.modules.synthesis.service import (
    get_monitoring_matrix as service_get_monitoring_matrix,
)

router = APIRouter(prefix="/evaluations", tags=["synthesis"])


@router.get("/{evaluation_id}/results", response_model=EvaluationResultsResponse)
def get_evaluation_results(
    evaluation_id: uuid.UUID,
    current_user=Depends(require_authenticated_user),
    db=Depends(get_db_session),
):
    try:
        return service_get_evaluation_results(evaluation_id, current_user.id, db=db)
    except EvaluationResultsNotFoundError:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    except EvaluationResultIntegrityError:
        raise HTTPException(
            status_code=500, detail="Evaluation results failed integrity verification"
        )


@router.get("/matrix", response_model=MatrixListResponse)
def get_monitoring_matrix(
    program: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(require_admin),
    db=Depends(get_db_session),
):
    try:
        return service_get_monitoring_matrix(program, status, page, page_size, db=db)
    except UnsupportedProgramFilterError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


__all__ = ["router"]
