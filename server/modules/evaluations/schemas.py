"""
Evaluations Pydantic schemas. Request/response objects for evaluation endpoints.
"""

from __future__ import annotations
from datetime import datetime
from uuid import UUID
from typing import Optional

from pydantic import BaseModel, Field
from server.modules.evaluations.models import EvaluationStatus

class EvaluationSubmitRequest(BaseModel):
    document_id: UUID = Field(..., description="ID of the document to evaluate.")
    # Optionally extend later with evaluation parameters (rubric, etc)

class EvaluationResponse(BaseModel):
    evaluation_id: UUID
    document_id: UUID
    status: EvaluationStatus
    error_message: Optional[str] = None
    submitted_by: Optional[UUID] = Field(None, description="User who submitted job.")
    submitted_at: datetime
    completed_at: Optional[datetime] = None

class EvaluationListItem(BaseModel):
    evaluation_id: UUID
    document_id: UUID
    status: EvaluationStatus
    submitted_at: datetime
    completed_at: Optional[datetime] = None

class EvaluationListResponse(BaseModel):
    items: list[EvaluationListItem]
    total: int
    page: int = Field(ge=1, default=1)
    page_size: int = Field(ge=1, le=200, default=20)

class EvaluationStatusResponse(BaseModel):
    evaluation_id: UUID
    status: EvaluationStatus
    error_message: Optional[str] = None
    completed_at: Optional[datetime] = None

__all__ = [
    "EvaluationSubmitRequest", "EvaluationResponse", "EvaluationListItem", "EvaluationListResponse", "EvaluationStatusResponse"
]
