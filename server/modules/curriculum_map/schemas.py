# server/modules/curriculum_map/schemas.py
"""Pydantic schemas for curriculum-map endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CourseResponse(BaseModel):
    course_id: UUID
    course_code: str
    course_title: str
    program: str


class CourseListResponse(BaseModel):
    items: list[CourseResponse]


class ObjectiveResultResponse(BaseModel):
    code: str
    description: str
    expected_level: str
    is_addressed: bool
    observed_level: str | None = None
    status: str
    evidence: str | None = None
    evidence_page: int | None = None


class AlignmentCheckSummary(BaseModel):
    total_mapped_objectives: int
    match: int
    under_developed: int
    over_developed: int
    not_addressed: int
    #: Absence observed only within a bounded (page-limited) evaluation --
    #: never a whole-document "not addressed" claim. Legacy checks without
    #: this key default to 0.
    not_observed: int = 0


class RunAlignmentCheckRequest(BaseModel):
    document_id: UUID
    course_id: UUID


class AlignmentCheckResponse(BaseModel):
    check_id: UUID
    document_id: UUID
    course_id: UUID
    course_title: str
    run_at: datetime
    model_name: str | None = None
    objective_results: list[ObjectiveResultResponse]
    summary: AlignmentCheckSummary
    success: bool
    error_message: str | None = None


class AlignmentCheckListItemResponse(BaseModel):
    check_id: UUID
    document_id: UUID
    document_title: str
    course_id: UUID
    course_title: str
    run_at: datetime
    success: bool
    error_message: str | None = None
    summary: AlignmentCheckSummary


class AlignmentCheckListResponse(BaseModel):
    items: list[AlignmentCheckListItemResponse]
    total: int
    page: int
    page_size: int


class DocumentPageResponse(BaseModel):
    page_number: int
    text: str


class DocumentPagesResponse(BaseModel):
    pages: list[DocumentPageResponse] = Field(default_factory=list)


__all__ = [
    "CourseResponse",
    "CourseListResponse",
    "ObjectiveResultResponse",
    "AlignmentCheckSummary",
    "RunAlignmentCheckRequest",
    "AlignmentCheckResponse",
    "AlignmentCheckListItemResponse",
    "AlignmentCheckListResponse",
    "DocumentPageResponse",
    "DocumentPagesResponse",
]
