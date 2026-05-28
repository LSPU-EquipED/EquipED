"""Admin routes for prompt management and preference log auditing."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError

from server.core.database import get_db_session
from server.modules.auth.dependencies import require_admin, require_authenticated_user
from server.modules.admin.schemas import (
    AdminUserCreateRequest,
    AdminUserListResponse,
    AdminUserResponse,
    PreferenceLogListResponse,
    PreferenceLogResponse,
    PromptCreate,
    PromptVersionListResponse,
    PromptVersionResponse,
    SystemSummaryResponse,
)
from server.modules.admin.service import (
    create_admin_user,
    create_prompt_version,
    get_system_summary,
    list_preference_logs,
    list_prompt_versions,
    list_users,
    revert_prompt_version,
)
from server.modules.auth.service import AuthenticatedUser

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/prompts/{agent_id}", response_model=PromptVersionListResponse)
def get_prompt_versions(
    agent_id: str,
    current_user: AuthenticatedUser = Depends(require_admin),
    db = Depends(get_db_session),
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


@router.post("/prompts/{agent_id}", response_model=PromptVersionResponse, status_code=status.HTTP_201_CREATED)
def create_prompt(
    agent_id: str,
    body: PromptCreate,
    current_user: AuthenticatedUser = Depends(require_admin),
    db = Depends(get_db_session),
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
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)
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


@router.post("/prompts/{agent_id}/revert/{version_id}", response_model=PromptVersionResponse, status_code=status.HTTP_201_CREATED)
def revert_prompt(
    agent_id: str,
    version_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(require_admin),
    db = Depends(get_db_session),
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
    action: str | None = Query(None, description="Filter by action: ACCEPT, REJECT, EDIT"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedUser = Depends(require_admin),
    db = Depends(get_db_session),
):
    items, total = list_preference_logs(db, action=action, page=page, page_size=page_size)

    return PreferenceLogListResponse(
        items=[
            PreferenceLogResponse(
                log_id=item.log_id,
                evaluation_id=item.evaluation_id,
                user_id=item.user_id,
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

@router.get("/users", response_model=AdminUserListResponse)
def get_users(
    current_user: AuthenticatedUser = Depends(require_admin),
    db = Depends(get_db_session),
):
    users = list_users(db)
    return AdminUserListResponse(
        items=[
            AdminUserResponse(
                user_id=u.user_id,
                name=u.name,
                email=u.email,
                role=u.role.value,
                is_active=u.is_active,
                created_at=u.created_at,
            )
            for u in users
        ],
        total=len(users),
    )


@router.post("/users", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
def create_user_endpoint(
    body: AdminUserCreateRequest,
    current_user: AuthenticatedUser = Depends(require_admin),
    db = Depends(get_db_session),
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

    return AdminUserResponse(
        user_id=new_user.user_id,
        name=new_user.name,
        email=new_user.email,
        role=new_user.role.value,
        is_active=new_user.is_active,
        created_at=new_user.created_at,
    )


# ---------------------------------------------------------------------------
# System summary
# ---------------------------------------------------------------------------

@router.get("/summary", response_model=SystemSummaryResponse)
def get_summary(
    current_user: AuthenticatedUser = Depends(require_admin),
    db = Depends(get_db_session),
):
    counts = get_system_summary(db)
    return SystemSummaryResponse(**counts)


__all__ = ["router"]
