"""Public request and response contracts for standalone syllabus alignment."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SyllabusAlignmentCreateRequest(BaseModel):
    slm_document_id: UUID
    syllabus_document_id: UUID


class SyllabusAlignmentRunResponse(BaseModel):
    alignment_id: UUID
    slm_document_id: UUID
    slm_title: str | None = None
    syllabus_document_id: UUID
    syllabus_title: str | None = None
    requested_by: UUID
    status: str
    alignment_level: str | None = None
    justification: str | None = None
    alignment_artifact: dict | None = None
    model_name: str | None = None
    provenance: dict | None = None
    error_message: str | None = None
    advisory_only: bool = True
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime


class SyllabusAlignmentSlmItem(BaseModel):
    document_id: UUID
    title: str
    course_title: str | None = None
    lesson_title: str | None = None
    program: str | None = None
    course_code: str | None = None
    processing_status: str
    uploaded_at: datetime
    evaluation_available: bool
    current_result: SyllabusAlignmentRunResponse | None = None


class SyllabusAlignmentSlmListResponse(BaseModel):
    items: list[SyllabusAlignmentSlmItem]
    total: int
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


__all__ = [
    "SyllabusAlignmentCreateRequest",
    "SyllabusAlignmentRunResponse",
    "SyllabusAlignmentSlmItem",
    "SyllabusAlignmentSlmListResponse",
]
