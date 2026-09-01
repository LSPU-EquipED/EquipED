"""Admin routes for prompt management and preference log auditing."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from server.core.config import get_settings
from server.core.database import get_db_session
from server.core.llm import probe_local_model_readiness
from server.modules.admin.model_validation_service import (
    create_model_validation,
    get_admin_evaluation,
    get_model_validation_criteria,
    get_model_validation_detail,
    get_model_validation_metrics,
    list_model_validations,
)
from server.modules.admin.models import ModelValidation
from server.modules.admin.prompt_service import (
    create_prompt_version,
    list_prompt_versions,
    revert_prompt_version,
)
from server.modules.admin.schemas import (
    AdminEvaluationResponse,
    AdminUserApprovalRequest,
    AdminUserCreateRequest,
    AdminUserListResponse,
    AdminUserResponse,
    AdminUserUpdateRequest,
    ModelValidationCreateRequest,
    ModelValidationCriteriaResponse,
    ModelValidationListResponse,
    ModelValidationMetricsResponse,
    ModelValidationResponse,
    PreferenceLogListResponse,
    PreferenceLogResponse,
    PromptCreate,
    PromptVersionListResponse,
    PromptVersionResponse,
    SystemSummaryResponse,
)
from server.modules.admin.system_service import get_system_summary
from server.modules.admin.user_service import (
    create_admin_user,
    deactivate_user,
    hard_delete_user,
    list_users,
    update_user,
)
from server.modules.auth.dependencies import require_admin
from server.modules.auth.email import send_status_email
from server.modules.auth.models import AccountStatus
from server.modules.auth.service import AuthenticatedUser
from server.modules.documents.exceptions import DocumentNotFoundError
from server.modules.evaluations.exceptions import InvalidEvaluationTargetError
from server.modules.evaluations.orchestrator import drain_evaluation_queue
from server.modules.evaluations.service import admission_schema_ready
from server.modules.feedback.service import list_preference_logs
from sqlalchemy.exc import IntegrityError

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)


@router.get("/prompts/{agent_id}", response_model=PromptVersionListResponse)
def get_prompt_versions(
    agent_id: str,
    current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
):
    try:
        versions = list_prompt_versions(agent_id, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    return PromptVersionListResponse(
        agent_id=agent_id,
        versions=[
            PromptVersionResponse(
                version_id=v.version_id,
                version_number=v.version_number,
                prompt_text=v.prompt_text,
                is_active=v.is_active,
                updated_by=str(v.updated_by) if v.updated_by else None,
                motivation=v.motivation,
                created_at=v.created_at,
            )
            for v in versions
        ],
        total=len(versions),
    )


@router.post(
    "/prompts/{agent_id}",
    response_model=PromptVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_prompt(
    agent_id: str,
    body: PromptCreate,
    current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
):
    try:
        new_version = create_prompt_version(
            agent_id=agent_id,
            prompt_text=body.prompt_text,
            updated_by=current_user.id,
            motivation=body.motivation,
            db=db,
        )
    except ValueError as e:
        msg = str(e)
        if "Unknown agent_id" in msg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        if "must not be empty" in msg:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg
            )
        raise

    db.commit()
    return PromptVersionResponse(
        version_id=new_version.version_id,
        version_number=new_version.version_number,
        prompt_text=new_version.prompt_text,
        is_active=new_version.is_active,
        updated_by=str(new_version.updated_by) if new_version.updated_by else None,
        motivation=new_version.motivation,
        created_at=new_version.created_at,
    )


@router.post(
    "/prompts/{agent_id}/revert/{version_id}",
    response_model=PromptVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def revert_prompt(
    agent_id: str,
    version_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
):
    try:
        reverted = revert_prompt_version(
            agent_id=agent_id,
            version_id=version_id,
            updated_by=current_user.id,
            db=db,
        )
    except ValueError as e:
        msg = str(e)
        if "not found" in msg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise

    db.commit()
    return PromptVersionResponse(
        version_id=reverted.version_id,
        version_number=reverted.version_number,
        prompt_text=reverted.prompt_text,
        is_active=reverted.is_active,
        updated_by=str(reverted.updated_by) if reverted.updated_by else None,
        motivation=reverted.motivation,
        created_at=reverted.created_at,
    )


@router.get("/preferences", response_model=PreferenceLogListResponse)
def get_preferences(
    action: str | None = Query(
        None, description="Filter by action: ACCEPT, REJECT, EDIT"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
):
    items, total = list_preference_logs(
        db, action=action, page=page, page_size=page_size
    )

    return PreferenceLogListResponse(
        items=[
            PreferenceLogResponse(
                log_id=item.log_id,
                evaluation_id=item.evaluation_id,
                user_id=item.user_id,
                agent_name=item.agent_name,
                criterion_id=item.criterion_id,
                action=item.action,
                edited_json=item.edited_json,
                notes=item.notes,
                created_at=item.created_at,
            )
            for item in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------


def _map_admin_user_response(
    user: Any, *, notification_warning: str | None = None
) -> AdminUserResponse:
    role_value = user.role.value if hasattr(user.role, "value") else str(user.role)
    return AdminUserResponse(
        user_id=user.user_id,
        name=user.name,
        email=user.email,
        role=role_value,
        is_active=user.is_active,
        account_status=user.account_status,
        faculty_id=user.faculty_id,
        department=user.department,
        program=user.program,
        approved_at=user.approved_at,
        reviewed_at=user.reviewed_at,
        notification_warning=notification_warning,
        created_at=user.created_at,
    )


def _send_approval_status_notification(
    settings: Any,
    to_email: str,
    user_name: str,
    approved: bool,
) -> None:
    try:
        send_status_email(
            settings=settings,
            to=to_email,
            name=user_name,
            approved=approved,
        )
    except Exception:
        logger.warning("Account status notification delivery failed.")


@router.get("/users", response_model=AdminUserListResponse)
def get_users(
    current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
):
    users = list_users(db)
    return AdminUserListResponse(
        items=[_map_admin_user_response(u) for u in users],
        total=len(users),
    )


@router.post(
    "/users", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED
)
def create_user_endpoint(
    body: AdminUserCreateRequest,
    current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
):
    try:
        new_user = create_admin_user(
            db,
            name=body.name,
            email=body.email,
            password=body.password,
            role=body.role,
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A user with email {body.email} already exists",
        )
    db.commit()

    return _map_admin_user_response(new_user)


@router.put("/users/{user_id}", response_model=AdminUserResponse)
def update_user_endpoint(
    user_id: uuid.UUID,
    body: AdminUserUpdateRequest,
    current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
):
    try:
        updated = update_user(
            db,
            user_id,
            name=body.name,
            email=body.email,
            is_active=body.is_active,
            account_status=body.account_status,
            reviewed_by=current_user.id,
        )
    except ValueError as e:
        msg = str(e)
        if msg == "User not found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        if msg == "Email already in use":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg)
        raise

    db.commit()
    return _map_admin_user_response(updated)


@router.post("/users/{user_id}/approval", response_model=AdminUserResponse)
def set_user_approval(
    user_id: uuid.UUID,
    body: AdminUserApprovalRequest,
    background_tasks: BackgroundTasks,
    current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
    settings=Depends(get_settings),
):
    status_value = body.status
    if status_value not in {
        AccountStatus.APPROVED,
        AccountStatus.REJECTED,
        AccountStatus.SUSPENDED,
    }:
        raise HTTPException(status_code=422, detail="Unsupported account status")
    try:
        updated = update_user(
            db, user_id, account_status=status_value, reviewed_by=current_user.id
        )
        db.commit()
    except ValueError as e:
        db.rollback()
        msg = str(e)
        if msg == "User not found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise
    except Exception:
        db.rollback()
        raise

    previous = getattr(updated, "_previous_account_status", None)
    if previous != status_value and status_value in {
        AccountStatus.APPROVED,
        AccountStatus.REJECTED,
    }:
        background_tasks.add_task(
            _send_approval_status_notification,
            settings,
            updated.email,
            updated.name,
            status_value == AccountStatus.APPROVED,
        )

    return _map_admin_user_response(updated)


@router.delete("/users/{user_id}", response_model=AdminUserResponse)
def deactivate_user_endpoint(
    user_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
):
    try:
        deactivated = deactivate_user(db, user_id, reviewed_by=current_user.id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    db.commit()
    return _map_admin_user_response(deactivated)


@router.delete("/users/{user_id}/permanent", status_code=status.HTTP_204_NO_CONTENT)
def hard_delete_user_endpoint(
    user_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
):
    try:
        hard_delete_user(db, user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    db.commit()


# ---------------------------------------------------------------------------
# System summary
# ---------------------------------------------------------------------------


@router.get("/summary", response_model=SystemSummaryResponse)
def get_summary(
    current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
):
    counts = get_system_summary(db)
    return SystemSummaryResponse(**counts)


@router.get("/model-validations", response_model=ModelValidationListResponse)
def get_model_validations(
    current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
):
    items = list_model_validations(db)
    return ModelValidationListResponse(items=items, total=len(items))


@router.get(
    "/model-validations/criteria", response_model=ModelValidationCriteriaResponse
)
def get_model_validation_criterion_catalog(
    current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
):
    return get_model_validation_criteria(db)


@router.get("/model-validations/metrics", response_model=ModelValidationMetricsResponse)
def get_model_validation_metric_summary(
    current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
):
    return get_model_validation_metrics(db)


@router.post(
    "/model-validations",
    response_model=ModelValidationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def submit_model_validation(
    body: ModelValidationCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
):
    try:
        probe_local_model_readiness()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Local model is unavailable.",
        ) from exc
    if not admission_schema_ready(db):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Evaluation admission is unavailable.",
        )
    try:
        response = create_model_validation(
            body,
            created_by=current_user.id,
            created_by_role=current_user.role.value,
            db=db,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from exc
    except InvalidEvaluationTargetError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    background_tasks.add_task(drain_evaluation_queue)
    return response


@router.get(
    "/model-validations/{validation_id}",
    response_model=ModelValidationResponse,
)
def get_model_validation_detail_endpoint(
    validation_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
):
    item = get_model_validation_detail(validation_id, db)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Validation record not found.",
        )
    return item


@router.get(
    "/model-validations/{validation_id}/evaluation",
    response_model=AdminEvaluationResponse,
)
def get_validation_evaluation(
    validation_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
):
    """Admin-only view of the evaluation linked to a validation benchmark.

    Returns the evaluation detail regardless of which user submitted the
    original evaluation job. Faculty must use their own evaluation detail
    endpoint and remain blocked from cross-user access.
    """
    validation = db.get(ModelValidation, validation_id)
    if validation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Validation record not found.",
        )
    evaluation = get_admin_evaluation(validation.evaluation_id, db)
    if evaluation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Linked evaluation not found.",
        )
    return evaluation


__all__ = ["router"]
