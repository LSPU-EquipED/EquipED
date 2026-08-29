"""Admin routes for viewing and text-editing the active rubric sets.

Scope: read the active rubric tree and edit criterion / domain *text* in
place. Structural changes (adding, removing, renaming criterion codes,
versioning) are deliberately not exposed here -- the SME engine binds
criterion codes to Python scorers, so those need their own design.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from server.core.database import get_db_session
from server.modules.auth.dependencies import require_admin
from server.modules.auth.service import AuthenticatedUser

from .schemas import (
    RubricCriterionOut,
    RubricCriterionUpdate,
    RubricDomainOut,
    RubricDomainUpdate,
    RubricSetListResponse,
)
from .service import (
    get_rubric_sets_for_editor,
    update_criterion,
    update_domain_title,
)

router = APIRouter(prefix="/admin/rubrics", tags=["admin"])


@router.get("", response_model=RubricSetListResponse)
def list_rubric_sets(
    _current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
) -> RubricSetListResponse:
    return RubricSetListResponse(rubric_sets=get_rubric_sets_for_editor(db=db))


@router.patch("/criteria/{criterion_id}", response_model=RubricCriterionOut)
def patch_criterion(
    criterion_id: uuid.UUID,
    body: RubricCriterionUpdate,
    _current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
) -> RubricCriterionOut:
    try:
        criterion = update_criterion(
            db,
            criterion_id,
            description=body.description,
            scoring_rule=body.scoring_rule,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    db.commit()
    return RubricCriterionOut(
        rubric_criterion_id=criterion.rubric_criterion_id,
        criterion_code=criterion.criterion_code,
        title=criterion.title,
        description=criterion.description,
        scoring_rule=criterion.scoring_rule,
        display_order=criterion.display_order,
    )


@router.patch("/domains/{domain_id}", response_model=RubricDomainOut)
def patch_domain(
    domain_id: uuid.UUID,
    body: RubricDomainUpdate,
    _current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
) -> RubricDomainOut:
    try:
        domain = update_domain_title(db, domain_id, title=body.title)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    db.commit()
    return RubricDomainOut(
        rubric_domain_id=domain.rubric_domain_id,
        code=domain.code,
        title=domain.title,
        display_order=domain.display_order,
        criteria=[],
    )
