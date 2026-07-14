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
    "policy",
)

# Source types that are institution-shared references (not SLMs or rubrics)
REFERENCE_SOURCE_TYPES = frozenset({"syllabus", "curriculum"})

# Source types that are policy documents (distinct from shared references)
POLICY_SOURCE_TYPES = frozenset({"policy"})

PROCESSING_STATUSES = ("PENDING", "PROCESSING", "PROCESSED", "FAILED")


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
    policy_area: str | None = None
    section_ref: str | None = None
    chunk_index: int | None = None


class DocumentChunkResponse(BaseModel):
    chunk_id: UUID
    document_id: UUID
    source_type: str
    agent_domain: str
    page_number: int
    text: str
    token_count: int
    is_ocr: bool
    policy_area: str | None = None
    section_ref: str | None = None
    chunk_index: int | None = None


class PolicyLibraryItem(BaseModel):
    """Lightweight policy item with computed health for the admin policy library."""
    document_id: UUID
    title: str
    source_type: str
    policy_area: str | None = None
    program: str | None = None
    course_code: str | None = None
    academic_year: str | None = None
    page_count: int | None = None
    uploaded_at: datetime
    uploaded_by: UUID | None = None
    processing_status: str
    file_exists: bool
    chunk_count: int
    chroma_available: bool
    embedding_ready: bool
    source_healthy: bool


class PolicyLibraryResponse(BaseModel):
    items: list[PolicyLibraryItem]
    total: int


class PolicyDeleteResponse(BaseModel):
    document_id: UUID
    deleted: bool
    details: dict[str, object] = Field(default_factory=dict)


class PolicyRebuildResponse(BaseModel):
    document_id: UUID
    rebuilt: bool
    chunk_count: int = 0
    details: dict[str, object] = Field(default_factory=dict)


class DocumentUploadResponse(BaseModel):
    document_id: UUID
    title: str
    course_title: str | None = None
    lesson_title: str | None = None
    source_type: str
    policy_area: str | None = None
    processing_status: str
    academic_year: str | None = None
    course_code: str | None = None
    structured_summary: str | None = None
    evaluation_readiness: str | None = None
    error_message: str | None = None


class DocumentResponse(BaseModel):
    document_id: UUID
    title: str
    course_title: str | None = None
    lesson_title: str | None = None
    source_type: str
    policy_area: str | None = None
    program: str | None = None
    academic_year: str | None = None
    course_code: str | None = None
    page_count: int | None = None
    processing_status: str
    has_ocr_pages: bool
    uploaded_at: datetime
    uploaded_by: UUID | None
    structured_summary: str | None = None
    structured_outline: list[dict[str, object]] | None = None
    section_summaries: list[dict[str, object]] | None = None
    key_facts: dict[str, object] | None = None
    processing_warnings: list[str] | None = None
    evaluation_readiness: str | None = None
    chunks: list[DocumentChunkResponse] = Field(default_factory=list)


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)


class TFIDFWeight(BaseModel):
    term: str
    idf_weight: float


class ReferenceLibraryItem(BaseModel):
    """Lightweight reference item with computed health for the admin library."""
    document_id: UUID
    title: str
    source_type: str
    policy_area: str | None = None
    program: str | None = None
    course_code: str | None = None
    academic_year: str | None = None
    course_title: str | None = None
    lesson_title: str | None = None
    page_count: int | None = None
    uploaded_at: datetime
    uploaded_by: UUID | None = None
    processing_status: str
    file_exists: bool
    chunk_count: int
    chroma_available: bool
    embedding_ready: bool


class ReferenceLibraryResponse(BaseModel):
    items: list[ReferenceLibraryItem]
    total: int


class ReferenceDeleteResponse(BaseModel):
    document_id: UUID
    deleted: bool
    details: dict[str, object] = Field(default_factory=dict)


class ReferenceRebuildResponse(BaseModel):
    document_id: UUID
    rebuilt: bool
    chunk_count: int = 0
    details: dict[str, object] = Field(default_factory=dict)


class CurriculumSuggestionItem(BaseModel):
    """A single curriculum candidate for program-driven suggestion."""
    document_id: UUID
    title: str
    program: str | None = None
    embedding_ready: bool
    match_reason: str = "selected_program"


class CurriculumSuggestionResponse(BaseModel):
    """Response for the curriculum suggestion endpoint.

    Returns SLM metadata, the confirmed program, and matching curriculum
    references split into ready (selectable) and unavailable groupings.
    """
    document_id: UUID
    detected_program: str | None = None
    selected_program: str
    detected_course_code: str | None = None
    detected_academic_year: str | None = None
    detected_lesson_title: str | None = None
    preferred_suggestion: CurriculumSuggestionItem | None = None
    curriculum_suggestions: list[CurriculumSuggestionItem] = Field(default_factory=list)
    unavailable_curricula: list[CurriculumSuggestionItem] = Field(default_factory=list)


__all__ = [
    "SOURCE_TYPES",
    "REFERENCE_SOURCE_TYPES",
    "POLICY_SOURCE_TYPES",
    "PROCESSING_STATUSES",
    "DocumentChunkData",
    "DocumentChunkResponse",
    "DocumentUploadResponse",
    "DocumentResponse",
    "DocumentListResponse",
    "TFIDFWeight",
    "ReferenceLibraryItem",
    "ReferenceLibraryResponse",
    "ReferenceDeleteResponse",
    "ReferenceRebuildResponse",
    "PolicyLibraryItem",
    "PolicyLibraryResponse",
    "PolicyDeleteResponse",
    "PolicyRebuildResponse",
    "CurriculumSuggestionItem",
    "CurriculumSuggestionResponse",
]
