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


def score_to_adjectival(score: float) -> str:
    """Convert a numeric score on a 1-4 scale to an adjectival rating.

    Based on the official institutional evaluation form:
        - 3.50-4.00 = Very Satisfactory
        - 2.50-3.49 = Satisfactory
        - 1.50-2.49 = Needs Improvement
        - 1.00-1.49 = Poor
    """
    if score >= 3.50:
        return "Very Satisfactory"
    elif score >= 2.50:
        return "Satisfactory"
    elif score >= 1.50:
        return "Needs Improvement"
    else:
        return "Poor"


class DomainScoreBlock(BaseModel):
    criteria: list[CriterionScoreItem]
    subtotal: float
    max_score: int
    status: str  # "OK" | "ERROR"
    adjectival_rating: str | None = None


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
    overall_score: float | None = None
    adjectival_rating: str | None = None
    domain_scores: dict[str, DomainScoreBlock]
    flags: list[EvaluationFlagItem] = Field(default_factory=list)
    active_agents: list[str]
    failed_agents: list[str]
    is_partial: bool = False
    evaluation_status: str
    submitted_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float | None = None


class MatrixRowItem(BaseModel):
    matrix_id: UUID
    document_id: UUID
    evaluation_id: UUID | None = None
    faculty_name: str | None = None
    program: str | None = None
    document_title: str | None = None
    evaluation_status: str
    synthesized_score: float | None = None
    adjectival_rating: str | None = None
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
    "score_to_adjectival",
]
