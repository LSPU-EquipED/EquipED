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


















class RoadmapSummaryResponse(BaseModel):
    roadmap_id: UUID
    program: str
    specialization: str | None = None
    version_number: int
    status: str
    created_at: datetime
    updated_at: datetime


class RoadmapCourseResponse(BaseModel):
    id: UUID
    course_code: str
    course_title: str
    course_status: str
    tech_stack: str | None = None
    competency_stage: str | None = None
    learning_outcomes_summary: str | None = None


class RoadmapYearResponse(BaseModel):
    year_id: UUID
    year_number: int
    semester: int | None = None
    label: str | None = None
    description: str | None = None
    courses: list[RoadmapCourseResponse] = Field(default_factory=list)


class RoadmapDetailResponse(BaseModel):
    roadmap_id: UUID
    program: str
    specialization: str | None = None
    version_number: int
    status: str
    years: list[RoadmapYearResponse] = Field(default_factory=list)


class RoadmapListResponse(BaseModel):
    items: list[RoadmapSummaryResponse]
    total: int


__all__ = [
    "CourseResponse",
    "CourseListResponse",
    "RoadmapSummaryResponse",
    "RoadmapCourseResponse",
    "RoadmapYearResponse",
    "RoadmapDetailResponse",
    "RoadmapListResponse",
]
