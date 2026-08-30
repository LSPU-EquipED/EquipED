"""Synthesis schemas — evaluation results and monitoring matrix."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field
from server.modules.rubrics.presentation import (
    EvaluationFormCriterionPresentation,
    EvaluationFormDomainPresentation,
    EvaluationFormPresentation,
)


class ReviewerCorrection(BaseModel):
    action: Literal["EDIT", "REJECT"]
    score: int | None = None
    justification: str | None = None


class CriterionScoreItem(BaseModel):
    rubric_criterion_id: UUID | None = None
    criterion_id: str
    criterion_text: str
    description: str | None = None
    display_order: int | None = None
    score: int
    justification: str
    evidence: str | None = None
    is_ungrounded: bool = False
    reviewer_correction: ReviewerCorrection | None = None


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
    form_snapshot_id: UUID | None = None
    rubric_set_id: UUID | None = None
    version: int | None = None
    snapshot_hash: str | None = None
    adapter_key: str | None = None
    adapter_version: int | None = None
    domain_id: UUID | None = None
    domain_name: str | None = None
    domain_display_order: int | None = None
    criteria: list[CriterionScoreItem]
    subtotal: float
    max_score: int
    status: str  # "OK" | "ERROR"
    adjectival_rating: str | None = None
    summary: str = ""


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
    syllabus_id: UUID | None = None
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
    partial_reason: str | None = None
    evaluation_status: str
    submitted_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    forms: dict[str, EvaluationFormPresentation] = Field(default_factory=dict)
    legacy_notice: str | None = None


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
    "ReviewerCorrection",
    "DomainScoreBlock",
    "EvaluationFormCriterionPresentation",
    "EvaluationFormDomainPresentation",
    "EvaluationFormPresentation",
    "EvaluationResultsResponse",
    "EvaluationFlagItem",
    "MatrixRowItem",
    "MatrixListResponse",
    "score_to_adjectival",
]
