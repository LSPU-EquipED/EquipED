"""Authenticated endpoints for standalone syllabus alignment."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from server.core.database import get_db_session
from server.modules.alignment.syllabus.exceptions import (
    InvalidSyllabusAlignmentTargetError,
    SyllabusAlignmentNotFoundError,
)
from server.modules.alignment.syllabus.schemas import (
    SyllabusAlignmentCreateRequest,
    SyllabusAlignmentRunResponse,
    SyllabusAlignmentSlmListResponse,
)
from server.modules.alignment.syllabus.service import (
    create_syllabus_alignment,
    get_current_syllabus_alignment,
    get_syllabus_alignment,
    list_alignment_slms,
)
from server.modules.auth.dependencies import require_authenticated_user
from server.modules.auth.service import AuthenticatedUser

router = APIRouter(prefix="/syllabus-alignments", tags=["syllabus-alignments"])


@router.post(
    "",
    response_model=SyllabusAlignmentRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_alignment(
    request: SyllabusAlignmentCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any = Depends(get_db_session),
) -> SyllabusAlignmentRunResponse:
    try:
        return create_syllabus_alignment(
            db,
            slm_document_id=request.slm_document_id,
            syllabus_document_id=request.syllabus_document_id,
            requested_by=current_user.id,
            background_tasks=background_tasks,
        )
    except SyllabusAlignmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidSyllabusAlignmentTargetError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/slms", response_model=SyllabusAlignmentSlmListResponse)
def list_slms(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any = Depends(get_db_session),
) -> SyllabusAlignmentSlmListResponse:
    return list_alignment_slms(
        db, requested_by=current_user.id, page=page, page_size=page_size
    )


@router.get("/current", response_model=SyllabusAlignmentRunResponse | None)
def get_current_alignment(
    slm_document_id: UUID,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any = Depends(get_db_session),
) -> SyllabusAlignmentRunResponse | None:
    try:
        return get_current_syllabus_alignment(
            db,
            slm_document_id=slm_document_id,
            requested_by=current_user.id,
        )
    except SyllabusAlignmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{alignment_id}", response_model=SyllabusAlignmentRunResponse)
def get_alignment(
    alignment_id: UUID,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any = Depends(get_db_session),
) -> SyllabusAlignmentRunResponse:
    try:
        return get_syllabus_alignment(db, alignment_id, current_user.id)
    except SyllabusAlignmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


__all__ = ["router"]
