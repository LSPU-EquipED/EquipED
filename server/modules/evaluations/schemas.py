"""
Evaluations Pydantic schemas. Request/response objects for evaluation endpoints.
Strict typing and status enforced per implementation plan.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field
from server.modules.evaluations.models import EvaluationStatus


class EvaluationSubmitRequest(BaseModel):
    document_id: UUID = Field(..., description="ID of the document to evaluate.")
    syllabus_id: UUID | None = Field(None, description="ID of the syllabus document.")
    curriculum_id: UUID | None = Field(
        None, description="ID of the curriculum document."
    )
    target_agent: Literal["sme", "coordinator", "gad", "itso"] = Field(
        "sme",
        description="Targeted specialist agent for this evaluation job.",
    )
    partial_without_curriculum: bool = Field(
        False,
        description=(
            "Deprecated: single-agent evaluations are 100% complete for the "
            "targeted domain. Retained for backward compatibility."
        ),
    )
    confirmed_program: str = Field(
        ..., min_length=1, max_length=50, description="Confirmed academic program code."
    )


class EvaluationResponse(BaseModel):
    evaluation_id: UUID
    document_id: UUID
    syllabus_id: UUID | None
    curriculum_id: UUID | None
    status: EvaluationStatus
    error_message: str | None = None
    target_agent: str = "all"
    partial_without_curriculum: bool = False
    partial_reason: str | None = None
    confirmed_program: str | None = None
    submitted_by: UUID | None = Field(None, description="User who submitted job.")
    submitted_at: datetime
    completed_at: datetime | None = None
    duration_seconds: float | None = None

class EvaluationListItem(BaseModel):
    evaluation_id: UUID
    document_id: UUID
    document_title: str | None = None
    syllabus_id: UUID | None
    curriculum_id: UUID | None
    status: EvaluationStatus
    target_agent: str = "all"
    partial_without_curriculum: bool = False
    partial_reason: str | None = None
    confirmed_program: str | None = None
    submitted_at: datetime
    completed_at: datetime | None = None
    duration_seconds: float | None = None


class EvaluationListResponse(BaseModel):
    items: list[EvaluationListItem]
    total: int
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)

class EvaluationStatusResponse(BaseModel):
    evaluation_id: UUID
    status: EvaluationStatus
    error_message: str | None = None
    target_agent: str = "all"
    partial_without_curriculum: bool = False
    partial_reason: str | None = None
    completed_at: datetime | None = None
    duration_seconds: float | None = None


class LatestEvaluationItem(BaseModel):
    document_id: UUID
    evaluation_id: UUID
    status: EvaluationStatus
    target_agent: str
    submitted_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None


class LatestEvaluationsResponse(BaseModel):
    items: list[LatestEvaluationItem]


__all__ = [
    "EvaluationSubmitRequest",
    "EvaluationResponse",
    "EvaluationListItem",
    "EvaluationListResponse",
    "EvaluationStatusResponse",
    "LatestEvaluationItem",
    "LatestEvaluationsResponse",
]
