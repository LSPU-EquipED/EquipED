"""Pydantic schemas and contracts for documents endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

SOURCE_TYPES = (
    "slm",
    "syllabus",
    "rubric_sme",
    "rubric_coord",
    "rubric_gad",
    "rubric_itso",
    "curriculum",
)

PROCESSING_STATUSES = ("PENDING", "PROCESSED", "FAILED")


class DocumentChunkData(BaseModel):
    """Layer 1 contract for chunks emitted by ingestion."""

    chunk_id: UUID
    document_id: UUID
    source_type: str
    agent_domain: str
    page_number: int
    text: str
    token_count: int
    is_ocr: bool


class DocumentUploadResponse(BaseModel):
    document_id: UUID
    title: str
    course_title: str | None = None
    lesson_title: str | None = None
    source_type: str
    processing_status: str


class DocumentResponse(BaseModel):
    document_id: UUID
    title: str
    course_title: str | None = None
    lesson_title: str | None = None
    source_type: str
    program: str | None = None
    page_count: int | None = None
    processing_status: str
    has_ocr_pages: bool
    uploaded_at: datetime
    uploaded_by: UUID | None


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)


class TFIDFWeight(BaseModel):
    term: str
    idf_weight: float


__all__ = [
    "SOURCE_TYPES",
    "PROCESSING_STATUSES",
    "DocumentChunkData",
    "DocumentUploadResponse",
    "DocumentResponse",
    "DocumentListResponse",
    "TFIDFWeight",
]
