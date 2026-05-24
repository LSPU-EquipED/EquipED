"""Synthesis schemas — evaluation results and monitoring matrix."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CriterionScoreItem(BaseModel):
    criterion_id: str
    criterion_text: str
    score: int
    justification: str
    evidence: str | None = None
    chunk_ids: str | None = None


class DomainScoreBlock(BaseModel):
    criteria: list[CriterionScoreItem]
    subtotal: float
    max_score: int
    status: str  # "OK" | "ERROR"


class EvaluationFlagItem(BaseModel):
    flag_id: UUID
    evaluation_id: UUID
    agent_id: str
    criterion_id: str
    criterion_text: str
    score: int
    justification: str | None = None
    chunk_id: UUID | None = None


class EvaluationResultsResponse(BaseModel):
    evaluation_id: UUID
    document_id: UUID
    document_title: str | None = None
    program: str | None = None
    synthesized_score: float
    domain_scores: dict[str, DomainScoreBlock]
    flags: list[EvaluationFlagItem] = Field(default_factory=list)
    active_agents: list[str]
    failed_agents: list[str]
    is_partial: bool = False
    evaluation_status: str
    completed_at: datetime | None = None


class MatrixRowItem(BaseModel):
    matrix_id: UUID
    document_id: UUID
    evaluation_id: UUID | None = None
    faculty_name: str | None = None
    program: str | None = None
    document_title: str | None = None
    evaluation_status: str
    synthesized_score: float | None = None
    domain_scores: dict[str, DomainScoreBlock] | None = None
    flag_count: int = 0
    feedback_status: str = "NO_FEEDBACK"
    last_updated: datetime


class MatrixListResponse(BaseModel):
    items: list[MatrixRowItem]
    total: int
    page: int
    page_size: int


__all__ = [
    "CriterionScoreItem",
    "DomainScoreBlock",
    "EvaluationResultsResponse",
    "EvaluationFlagItem",
    "MatrixRowItem",
    "MatrixListResponse",
]
