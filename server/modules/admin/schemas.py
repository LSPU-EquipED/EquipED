"""Pydantic schemas for admin prompt management and preference log views."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field
from server.modules.evaluations.models import EvaluationStatus


class PromptCreate(BaseModel):
    """Request body for creating a new prompt version."""

    prompt_text: str = Field(
        ..., min_length=1, max_length=10000, description="The prompt text content"
    )
    motivation: str | None = Field(None, description="Reason for this prompt update")


class PromptVersionResponse(BaseModel):
    """A single prompt version in the version history list."""

    version_id: uuid.UUID
    version_number: int
    prompt_text: str
    is_active: bool
    updated_by: str | None = None
    motivation: str | None = None
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
    edited_json: dict | None = None
    notes: str | None = None
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


class AdminUserUpdateRequest(BaseModel):
    """Request body for updating an existing user (admin-only)."""

    name: str | None = Field(None, min_length=1, max_length=300)
    email: str | None = Field(None, min_length=1, max_length=300)
    is_active: bool | None = None


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


class ExpectedCriterionScoreCreate(BaseModel):
    agent_id: Literal["sme", "coordinator", "gad", "itso"]
    criterion_id: str = Field(min_length=1, max_length=100)
    expected_score: int = Field(ge=1, le=4)


class ModelValidationCreateRequest(BaseModel):
    """Create a benchmark without exposing expected criterion scores to agents.

    Curriculum selection is retired: every new validation run is a
    curriculum-retired partial evaluation of an admin-uploaded SLM.
    """

    document_id: uuid.UUID
    syllabus_id: uuid.UUID | None = None
    partial_without_curriculum: bool = False
    expected_scores: list[ExpectedCriterionScoreCreate] = Field(min_length=1)


class ModelValidationCriterionScoreResponse(BaseModel):
    expected_score_id: uuid.UUID
    agent_id: str
    criterion_id: str
    criterion_title: str
    expected_score: int
    actual_score: int | None = None
    absolute_error: float | None = None


class ModelValidationCriterionDefinition(BaseModel):
    criterion_id: str
    title: str
    description: str
    domain_title: str


class ModelValidationAgentCriteria(BaseModel):
    agent_id: str
    agent_name: str
    rubric_version: int
    criteria: list[ModelValidationCriterionDefinition]


class ModelValidationCriteriaResponse(BaseModel):
    agents: list[ModelValidationAgentCriteria]
    total_criteria: int


class ModelValidationResponse(BaseModel):
    validation_id: uuid.UUID
    evaluation_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str | None = None
    partial_without_curriculum: bool = False
    criterion_scores: list[ModelValidationCriterionScoreResponse]
    absolute_error: float | None = None
    latency_seconds: float | None = None
    score_perplexity: float | None = None
    toxicity_score: float | None = None
    toxicity_label: str | None = None
    toxicity_explanation: str | None = None
    toxicity_model: str | None = None
    toxicity_error: str | None = None
    status: EvaluationStatus
    error_message: str | None = None
    created_at: datetime


class ModelValidationListResponse(BaseModel):
    items: list[ModelValidationResponse]
    total: int


class ModelValidationMetricsResponse(BaseModel):
    completed_runs: int
    mean_absolute_error: float | None = None
    mean_latency_seconds: float | None = None
    score_perplexity: float | None = None
    mean_toxicity_score: float | None = None
    class_labels: list[str]
    confusion_matrix: list[list[int]]
    agent_confusion_matrices: dict[str, list[list[int]]] = Field(default_factory=dict)


class AdminEvaluationResponse(BaseModel):
    """Evaluation detail returned to admins (bypasses faculty ownership)."""

    evaluation_id: uuid.UUID
    document_id: uuid.UUID
    syllabus_id: uuid.UUID | None = None
    curriculum_id: uuid.UUID | None = None
    status: str
    error_message: str | None = None
    partial_without_curriculum: bool = False
    partial_reason: str | None = None
    confirmed_program: str | None = None
    submitted_by: uuid.UUID | None = None
    submitted_at: datetime
    completed_at: datetime | None = None
    duration_seconds: float | None = None


__all__ = [
    "PromptCreate",
    "PromptVersionResponse",
    "PromptVersionListResponse",
    "PreferenceLogResponse",
    "PreferenceLogListResponse",
    "AdminUserCreateRequest",
    "AdminUserUpdateRequest",
    "AdminUserResponse",
    "AdminUserListResponse",
    "SystemSummaryResponse",
    "ModelValidationCreateRequest",
    "ExpectedCriterionScoreCreate",
    "ModelValidationCriterionScoreResponse",
    "ModelValidationCriterionDefinition",
    "ModelValidationAgentCriteria",
    "ModelValidationCriteriaResponse",
    "ModelValidationResponse",
    "ModelValidationListResponse",
    "ModelValidationMetricsResponse",
    "AdminEvaluationResponse",
]
