"""Routers for synthesis results and monitoring matrix views."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from server.core.database import get_db_session
from server.modules.auth.dependencies import require_admin, require_authenticated_user
from server.modules.evaluations.exceptions import EvaluationNotFoundError
from server.modules.evaluations.itso.assessment_service import reject_legacy_v2_read
from server.modules.evaluations.itso.exceptions import ITSOError
from server.modules.synthesis.exceptions import (
    EvaluationResultIntegrityError,
    EvaluationResultsNotFoundError,
    MonitoringMatrixNotFoundError,
    UnsupportedProgramFilterError,
)
from server.modules.synthesis.schemas import (
    EvaluationResultsResponse,
    MasterSynthesisDetailResponse,
    MatrixListResponse,
)
from server.modules.synthesis.service import (
    get_evaluation_results as service_get_evaluation_results,
)
from server.modules.synthesis.service import (
    get_master_synthesis_detail as service_get_master_synthesis_detail,
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
        user_role = (
            current_user.role.value
            if hasattr(current_user.role, "value")
            else str(current_user.role)
        )
        reject_legacy_v2_read(
            db,
            evaluation_id=evaluation_id,
            actor_id=current_user.id,
            role=user_role,
            evaluator_permissions=getattr(current_user, "evaluator_permissions", None),
        )
        return service_get_evaluation_results(
            evaluation_id,
            current_user.id,
            db=db,
            evaluator_permissions=getattr(current_user, "evaluator_permissions", None),
            current_user_role=user_role,
        )
    except ITSOError as exc:
        raise HTTPException(status_code=exc.status, detail={"code": exc.code})
    except (EvaluationResultsNotFoundError, EvaluationNotFoundError):
        raise HTTPException(status_code=404, detail="Evaluation not found")
    except EvaluationResultIntegrityError:
        raise HTTPException(
            status_code=500, detail="Evaluation results failed integrity verification"
        )


@router.get("/matrix", response_model=MatrixListResponse)
def get_monitoring_matrix(
    program: str | None = Query(None),
    status: str | None = Query(None),
    search: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(require_admin),
    db=Depends(get_db_session),
):
    try:
        return service_get_monitoring_matrix(
            program, status, page, page_size, db=db, search=search
        )
    except ITSOError as exc:
        raise HTTPException(status_code=exc.status, detail={"code": exc.code})
    except UnsupportedProgramFilterError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/matrix/{document_id}", response_model=MasterSynthesisDetailResponse)
def get_master_synthesis_detail(
    document_id: uuid.UUID,
    current_user=Depends(require_admin),
    db=Depends(get_db_session),
) -> MasterSynthesisDetailResponse:
    try:
        return service_get_master_synthesis_detail(db=db, document_id=document_id)
    except ITSOError as exc:
        raise HTTPException(status_code=exc.status, detail={"code": exc.code})
    except MonitoringMatrixNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


__all__ = ["router"]
