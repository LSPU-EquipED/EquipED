"""Admin routes for dynamic CID evaluation forms lifecycle and authoring.

Scope:
- View active rubric sets or all versioned revisions with active pointers.
- Draft creation, validation, atomic reorder, publication, activation, retirement.
- Add, update, and delete domains and criteria in draft revisions.
- Strictly immutable published and retired definitions return HTTP 409 Conflict.
- Transaction boundary: single commit on success, rollback on failure.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from server.core.database import get_db_session
from server.modules.auth.dependencies import require_admin
from server.modules.auth.service import AuthenticatedUser

from .exceptions import (
    RubricConflictError,
    RubricNotFoundError,
    RubricValidationError,
)
from .schemas import (
    RubricActivationOut,
    RubricCriterionCreate,
    RubricCriterionMoveRequest,
    RubricCriterionOut,
    RubricCriterionUpdate,
    RubricDomainCreate,
    RubricDomainOut,
    RubricDomainUpdate,
    RubricPublishRequest,
    RubricReorderRequest,
    RubricRevisionsResponse,
    RubricSetListResponse,
    RubricSetOut,
    ValidationIssueOut,
    ValidationReportOut,
)
from .service import (
    _UNSET,
    activate_revision_by_id,
    create_criterion,
    create_domain,
    create_draft_for_agent,
    delete_criterion,
    delete_domain,
    delete_draft,
    get_all_revisions,
    get_revision_by_id,
    get_rubric_sets_for_editor,
    move_criterion,
    publish_revision,
    reorder_rubric_tree,
    retire_revision_by_id,
    update_criterion,
    update_domain,
    validate_draft_revision,
)

router = APIRouter(prefix="/admin/rubrics", tags=["admin"])


def _handle_validation_error(exc: RubricValidationError | ValueError) -> HTTPException:
    """Format structured 422 error response when validation report is available."""
    if isinstance(exc, RubricValidationError) and exc.report is not None:
        detail: dict[str, Any] = {
            "is_valid": exc.report.is_valid,
            "issues": [
                {
                    "path": i.path,
                    "code": i.code,
                    "message": i.message,
                    "severity": i.severity,
                }
                for i in exc.report.issues
            ],
            "estimated_prompt_chars": exc.report.estimated_prompt_chars,
            "criteria_count": exc.report.criteria_count,
        }
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail
        )
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
    )


# ---------------------------------------------------------------------------
# Revisions and Active Pointer Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=RubricSetListResponse)
def list_rubric_sets(
    all_revisions: bool = Query(False),
    agent_id: str | None = Query(None),
    _current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
) -> RubricSetListResponse:
    """Return active rubric sets (default) or all revisions if requested."""
    if all_revisions or agent_id is not None:
        data = get_all_revisions(db, agent_id=agent_id)
        return RubricSetListResponse(
            rubric_sets=[RubricSetOut.model_validate(s) for s in data["revisions"]],
            activations=data["active_pointers"],
        )
    raw_sets = get_rubric_sets_for_editor(db=db)
    return RubricSetListResponse(
        rubric_sets=[RubricSetOut.model_validate(s) for s in raw_sets]
    )


@router.get("/revisions", response_model=RubricRevisionsResponse)
def list_revisions(
    agent_id: str | None = Query(None),
    _current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
) -> RubricRevisionsResponse:
    """Return all rubric revisions with active pointer mapping."""
    data = get_all_revisions(db, agent_id=agent_id)
    return RubricRevisionsResponse(
        revisions=[RubricSetOut.model_validate(s) for s in data["revisions"]],
        active_pointers=data["active_pointers"],
    )


@router.get("/{rubric_set_id}", response_model=RubricSetOut)
def get_rubric_set_by_id(
    rubric_set_id: uuid.UUID,
    _current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
) -> RubricSetOut:
    """Load a specific rubric set revision fully nested."""
    try:
        data = get_revision_by_id(db, rubric_set_id)
        return RubricSetOut.model_validate(data)
    except RubricNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


# ---------------------------------------------------------------------------
# Draft Lifecycle Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/agents/{agent_id}/draft",
    response_model=RubricSetOut,
    status_code=status.HTTP_201_CREATED,
)
def create_draft(
    agent_id: str,
    current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
) -> RubricSetOut:
    """Clone the active published revision into a single editable draft."""
    try:
        draft_dict = create_draft_for_agent(db, agent_id, actor_id=current_user.id)
        db.commit()
        return RubricSetOut.model_validate(draft_dict)
    except RubricNotFoundError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except RubricConflictError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except Exception:
        db.rollback()
        raise


@router.delete("/{rubric_set_id}/draft", status_code=status.HTTP_204_NO_CONTENT)
def delete_draft_route(
    rubric_set_id: uuid.UUID,
    _current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
) -> None:
    """Delete a draft revision and its child domains/criteria."""
    try:
        delete_draft(db, rubric_set_id)
        db.commit()
    except RubricNotFoundError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except RubricConflictError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except Exception:
        db.rollback()
        raise


@router.post("/{rubric_set_id}/validate", response_model=ValidationReportOut)
def validate_draft_route(
    rubric_set_id: uuid.UUID,
    _current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
) -> ValidationReportOut:
    """Validate a draft revision against its capability manifest and prompt budget."""
    try:
        report = validate_draft_revision(db, rubric_set_id)
        return ValidationReportOut(
            is_valid=report.is_valid,
            issues=[
                ValidationIssueOut(
                    path=i.path,
                    code=i.code,
                    message=i.message,
                    severity=i.severity,
                )
                for i in report.issues
            ],
            estimated_prompt_chars=report.estimated_prompt_chars,
            criteria_count=report.criteria_count,
        )
    except RubricNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except (RubricValidationError, ValueError) as exc:
        raise _handle_validation_error(exc) from exc


@router.post("/{rubric_set_id}/publish", response_model=RubricSetOut)
def publish_revision_route(
    rubric_set_id: uuid.UUID,
    body: RubricPublishRequest = RubricPublishRequest(),
    current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
) -> RubricSetOut:
    """Publish a draft revision and optionally activate it atomically."""
    try:
        published_dict = publish_revision(
            db,
            rubric_set_id,
            actor_id=current_user.id,
            activate=body.activate,
        )
        db.commit()
        return RubricSetOut.model_validate(published_dict)
    except RubricNotFoundError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except RubricConflictError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except (RubricValidationError, ValueError) as exc:
        db.rollback()
        raise _handle_validation_error(exc) from exc
    except Exception:
        db.rollback()
        raise


@router.post("/{rubric_set_id}/activate", response_model=RubricActivationOut)
def activate_revision_route(
    rubric_set_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
) -> RubricActivationOut:
    """Activate an older published compatible revision (rollback)."""
    try:
        activation = activate_revision_by_id(
            db, rubric_set_id, actor_id=current_user.id
        )
        db.commit()
        return RubricActivationOut(
            agent_id=activation.agent_id,
            rubric_set_id=activation.rubric_set_id,
            updated_by=activation.updated_by,
            updated_at=activation.updated_at,
        )
    except RubricNotFoundError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except RubricConflictError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except (RubricValidationError, ValueError) as exc:
        db.rollback()
        raise _handle_validation_error(exc) from exc
    except Exception:
        db.rollback()
        raise


@router.post("/{rubric_set_id}/retire", response_model=RubricSetOut)
def retire_revision_route(
    rubric_set_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
) -> RubricSetOut:
    """Retire a non-active published revision."""
    try:
        retired_dict = retire_revision_by_id(
            db, rubric_set_id, actor_id=current_user.id
        )
        db.commit()
        return RubricSetOut.model_validate(retired_dict)
    except RubricNotFoundError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except RubricConflictError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except Exception:
        db.rollback()
        raise


@router.post("/{rubric_set_id}/reorder", response_model=RubricSetOut)
def reorder_rubric_tree_route(
    rubric_set_id: uuid.UUID,
    body: RubricReorderRequest,
    _current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
) -> RubricSetOut:
    """Ordering-only complete-tree reorder of domains and criteria."""
    try:
        reordered_dict = reorder_rubric_tree(
            db, rubric_set_id, domain_orders=body.domains
        )
        db.commit()
        return RubricSetOut.model_validate(reordered_dict)
    except RubricNotFoundError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except RubricConflictError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except (RubricValidationError, ValueError) as exc:
        db.rollback()
        raise _handle_validation_error(exc) from exc
    except Exception:
        db.rollback()
        raise


# ---------------------------------------------------------------------------
# Domain Child Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/{rubric_set_id}/domains",
    response_model=RubricDomainOut,
    status_code=status.HTTP_201_CREATED,
)
def create_domain_route(
    rubric_set_id: uuid.UUID,
    body: RubricDomainCreate,
    _current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
) -> RubricDomainOut:
    """Add a new domain to a draft rubric set."""
    try:
        domain = create_domain(
            db,
            rubric_set_id,
            code=body.code,
            title=body.title,
        )
        db.commit()
        return RubricDomainOut(
            rubric_domain_id=domain.rubric_domain_id,
            rubric_set_id=domain.rubric_set_id,
            code=domain.code,
            title=domain.title,
            display_order=domain.display_order,
            criteria=[],
        )
    except RubricNotFoundError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except RubricConflictError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except (RubricValidationError, ValueError) as exc:
        db.rollback()
        raise _handle_validation_error(exc) from exc
    except Exception:
        db.rollback()
        raise


@router.patch("/domains/{domain_id}", response_model=RubricDomainOut)
def patch_domain(
    domain_id: uuid.UUID,
    body: RubricDomainUpdate,
    _current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
) -> RubricDomainOut:
    """Update domain fields in a draft rubric set."""
    try:
        domain = update_domain(
            db,
            domain_id,
            title=body.title,
            code=body.code,
        )
        db.commit()
        return RubricDomainOut(
            rubric_domain_id=domain.rubric_domain_id,
            rubric_set_id=domain.rubric_set_id,
            code=domain.code,
            title=domain.title,
            display_order=domain.display_order,
            criteria=[],
        )
    except RubricNotFoundError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except RubricConflictError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except (RubricValidationError, ValueError) as exc:
        db.rollback()
        raise _handle_validation_error(exc) from exc
    except Exception:
        db.rollback()
        raise


@router.delete("/domains/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_domain_route(
    domain_id: uuid.UUID,
    _current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
) -> None:
    """Delete a domain and its child criteria from a draft rubric set."""
    try:
        delete_domain(db, domain_id)
        db.commit()
    except RubricNotFoundError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except RubricConflictError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except Exception:
        db.rollback()
        raise


# ---------------------------------------------------------------------------
# Criterion Child Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/domains/{domain_id}/criteria",
    response_model=RubricCriterionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_criterion_route(
    domain_id: uuid.UUID,
    body: RubricCriterionCreate,
    _current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
) -> RubricCriterionOut:
    """Add a new criterion to a domain in a draft rubric set."""
    try:
        criterion = create_criterion(
            db,
            domain_id,
            criterion_code=body.criterion_code,
            title=body.title,
            description=body.description,
            scoring_rule=body.scoring_rule,
            strategy_config=body.strategy_config,
        )
        db.commit()
        return RubricCriterionOut(
            rubric_criterion_id=criterion.rubric_criterion_id,
            rubric_domain_id=criterion.rubric_domain_id,
            criterion_code=criterion.criterion_code,
            title=criterion.title,
            description=criterion.description,
            scoring_rule=criterion.scoring_rule,
            scoring_strategy=criterion.scoring_strategy,
            strategy_config=criterion.strategy_config,
            display_order=criterion.display_order,
        )
    except RubricNotFoundError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except RubricConflictError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except (RubricValidationError, ValueError) as exc:
        db.rollback()
        raise _handle_validation_error(exc) from exc
    except Exception:
        db.rollback()
        raise


@router.patch("/criteria/{criterion_id}", response_model=RubricCriterionOut)
def patch_criterion(
    criterion_id: uuid.UUID,
    body: RubricCriterionUpdate,
    _current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
) -> RubricCriterionOut:
    """Update criterion fields in a draft rubric set."""
    try:
        scoring_rule_val: Any = (
            body.scoring_rule if "scoring_rule" in body.model_fields_set else _UNSET
        )
        criterion = update_criterion(
            db,
            criterion_id,
            description=body.description,
            scoring_rule=scoring_rule_val,
            title=body.title,
            criterion_code=body.criterion_code,
            strategy_config=body.strategy_config,
        )
        db.commit()
        return RubricCriterionOut(
            rubric_criterion_id=criterion.rubric_criterion_id,
            rubric_domain_id=criterion.rubric_domain_id,
            criterion_code=criterion.criterion_code,
            title=criterion.title,
            description=criterion.description,
            scoring_rule=criterion.scoring_rule,
            scoring_strategy=criterion.scoring_strategy,
            strategy_config=criterion.strategy_config,
            display_order=criterion.display_order,
        )
    except RubricNotFoundError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except RubricConflictError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except (RubricValidationError, ValueError) as exc:
        db.rollback()
        raise _handle_validation_error(exc) from exc
    except Exception:
        db.rollback()
        raise


@router.post("/criteria/{criterion_id}/move", response_model=RubricCriterionOut)
def move_criterion_route(
    criterion_id: uuid.UUID,
    body: RubricCriterionMoveRequest,
    _current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
) -> RubricCriterionOut:
    """Move one criterion to a destination domain in the same draft."""
    try:
        criterion = move_criterion(
            db,
            criterion_id,
            destination_domain_id=body.destination_domain_id,
        )
        db.commit()
        return RubricCriterionOut(
            rubric_criterion_id=criterion.rubric_criterion_id,
            rubric_domain_id=criterion.rubric_domain_id,
            criterion_code=criterion.criterion_code,
            title=criterion.title,
            description=criterion.description,
            scoring_rule=criterion.scoring_rule,
            scoring_strategy=criterion.scoring_strategy,
            strategy_config=criterion.strategy_config,
            display_order=criterion.display_order,
        )
    except RubricNotFoundError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except RubricConflictError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except (RubricValidationError, ValueError) as exc:
        db.rollback()
        raise _handle_validation_error(exc) from exc
    except Exception:
        db.rollback()
        raise


@router.delete("/criteria/{criterion_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_criterion_route(
    criterion_id: uuid.UUID,
    _current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
) -> None:
    """Delete a criterion from a draft rubric set."""
    try:
        delete_criterion(db, criterion_id)
        db.commit()
    except RubricNotFoundError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except RubricConflictError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except Exception:
        db.rollback()
        raise
