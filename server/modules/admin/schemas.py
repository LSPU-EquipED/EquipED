"""Pydantic schemas for admin prompt management and preference log views."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class PromptCreate(BaseModel):
    """Request body for creating a new prompt version."""

    prompt_text: str = Field(
        ..., min_length=1, max_length=10000, description="The prompt text content"
    )
    motivation: Optional[str] = Field(None, description="Reason for this prompt update")


class PromptVersionResponse(BaseModel):
    """A single prompt version in the version history list."""

    version_id: uuid.UUID
    version_number: int
    prompt_text: str
    is_active: bool
    updated_by: Optional[str] = None
    motivation: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PromptVersionListResponse(BaseModel):
    """List of prompt versions for an agent."""

    agent_id: str
    versions: list[PromptVersionResponse]
    total: int


class PreferenceLogResponse(BaseModel):
    """A single preference log entry."""

    log_id: uuid.UUID
    evaluation_id: uuid.UUID
    user_id: uuid.UUID
    action: Literal["ACCEPT", "REJECT", "EDIT"]
    edited_json: Optional[dict] = None
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PreferenceLogListResponse(BaseModel):
    """Paginated list of preference logs."""

    items: list[PreferenceLogResponse]
    total: int
    page: int
    page_size: int


class AdminUserCreateRequest(BaseModel):
    """Request body for creating a new user (admin-only)."""

    name: str = Field(..., min_length=1, max_length=300)
    email: str = Field(..., min_length=1, max_length=300)
    password: str = Field(..., min_length=1)
    role: Literal["admin", "faculty"] = Field(default="faculty")


class AdminUserResponse(BaseModel):
    """A single user record returned to admins."""

    user_id: uuid.UUID
    name: str
    email: str
    role: Literal["admin", "faculty"]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AdminUserListResponse(BaseModel):
    """List of all registered users."""

    items: list[AdminUserResponse]
    total: int


class SystemSummaryResponse(BaseModel):
    """System-wide metrics for the admin dashboard."""

    total_documents: int
    total_faculty: int
    active_evaluations: int
    failed_evaluations: int


__all__ = [
    "PromptCreate",
    "PromptVersionResponse",
    "PromptVersionListResponse",
    "PreferenceLogResponse",
    "PreferenceLogListResponse",
    "AdminUserCreateRequest",
    "AdminUserResponse",
    "AdminUserListResponse",
    "SystemSummaryResponse",
]
