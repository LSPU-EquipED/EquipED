"""
Evaluations Pydantic schemas. Request/response objects for evaluation endpoints.
Strict typing and status enforced per implementation plan.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field
from server.modules.evaluations.models import EvaluationStatus


class EvaluationSubmitRequest(BaseModel):
    document_id: UUID = Field(..., description="ID of the document to evaluate.")
    syllabus_id: UUID | None = Field(None, description="ID of the syllabus document.")
    curriculum_id: UUID | None = Field(None, description="ID of the curriculum document.")
    partial_without_curriculum: bool = Field(
        ...,
        description=(
            "Explicit intent to proceed without a curriculum reference. "
            "Must be explicitly set to True."
        ),
    )
    confirmed_program: str = Field(..., min_length=1, description="Confirmed academic program code.")

class EvaluationResponse(BaseModel):
    evaluation_id: UUID
    document_id: UUID
    syllabus_id: UUID | None
    curriculum_id: UUID | None
    status: EvaluationStatus
    error_message: str | None = None
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
    partial_without_curriculum: bool = False
    partial_reason: str | None = None
    completed_at: datetime | None = None
    duration_seconds: float | None = None

__all__ = [
    "EvaluationSubmitRequest", "EvaluationResponse", "EvaluationListItem", "EvaluationListResponse", "EvaluationStatusResponse"
]
