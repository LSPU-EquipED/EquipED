"""Synthesis schemas — evaluation results and monitoring matrix."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from equiped_harness.agents.coordinator.contracts import (
    CoordinatorAlignmentAdvisory,
    CoordinatorAlignmentJudgment,
)
from equiped_harness.agents.itso.compatibility.contracts import CriterionAssessment
from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag
from server.modules.rubrics.presentation import (
    EvaluationFormCriterionPresentation,
    EvaluationFormDomainPresentation,
    EvaluationFormPresentation,
)


class ReviewerCorrection(BaseModel):
    action: Literal["EDIT", "REJECT"]
    score: int | None = None
    justification: str | None = None


class RawMeasurementItemOut(BaseModel):
    """One extracted item (instance/qualifying unit) within a criterion's
    raw measurement -- what an SME/Coordinator reviewer can accept/reject
    at the item level. See server/modules/feedback/items.py."""

    item_id: str
    text: str
    included: bool
    rejected: bool = False


class ITSOResultPublicSource(BaseModel):
    number: int
    title: str | None = None
    url: str
    excerpt: str


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
    evidence_status: Literal["no_concern_detected", "rights_unverified"] | None = None
    public_sources: list[ITSOResultPublicSource] = Field(default_factory=list)
    reference_check_note: str | None = None
    reviewer_correction: ReviewerCorrection | None = None
    raw_items: list[RawMeasurementItemOut] | None = None
    corrected_score: int | None = None


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
    advisory_outputs: (
        CoordinatorAlignmentAdvisory | CoordinatorAlignmentJudgment | None
    ) = None
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


class ITSODomainScoreBlock(BaseModel):
    """Public whitelist: pure criteria contain facts, never model generations."""

    model_config = ConfigDict(extra="forbid", strict=True)
    contract: Literal["itso_evidence.v1"]
    evaluation_id: str
    criteria: list[CriterionAssessment] = Field(min_length=5, max_length=5)
    subtotal: float | None
    max_score: Literal[4]
    status: Literal["OK", "ERROR"]
    execution_status: Literal["COMPLETED", "FAILED"]
    scoring_complete: bool
    scored_count: int = Field(ge=0)
    unscored_count: int = Field(ge=0)
    issue_count: int = Field(ge=0)
    uncertainty_count: int = Field(ge=0)
    adjectival_rating: None = None


def _projection_version(value):
    contract = (
        value.get("contract")
        if isinstance(value, dict)
        else getattr(value, "contract", None)
    )
    return contract or "legacy.v1"


MatrixDomainScoreBlock = Annotated[
    Annotated[DomainScoreBlock, Tag("legacy.v1")]
    | Annotated[ITSODomainScoreBlock, Tag("itso_evidence.v1")],
    Discriminator(_projection_version),
]


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


class MatrixMetrics(BaseModel):
    completed_count: int
    passing_count: int
    flagged_count: int
    total_flags: int
    quality_pass_rate: float | None = None


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
    domain_scores: dict[str, MatrixDomainScoreBlock] | None = None
    flag_count: int = 0
    feedback_status: str = "NO_FEEDBACK"
    last_updated: datetime


class MatrixListResponse(BaseModel):
    items: list[MatrixRowItem]
    total: int
    page: int
    page_size: int
    metrics: MatrixMetrics


class EvaluatorAttribution(BaseModel):
    user_id: UUID | None = None
    name: str = "Unknown Author"
    email: str | None = None
    department: str | None = None


class MasterSynthesisPillar(BaseModel):
    advisory_outputs: (
        CoordinatorAlignmentAdvisory | CoordinatorAlignmentJudgment | None
    ) = None
    weight: float
    subtotal: float | None = None
    status: str
    criteria: list[CriterionScoreItem] = Field(default_factory=list)
    summary: str = ""
    evaluator: EvaluatorAttribution | None = None


class ITSOMasterSynthesisPillar(ITSODomainScoreBlock):
    status: Literal["COMPLETED", "FAILED"]
    weight: float
    evaluator: EvaluatorAttribution | None = None
    summary: str = ""


MasterPillar = Annotated[
    Annotated[MasterSynthesisPillar, Tag("legacy.v1")]
    | Annotated[ITSOMasterSynthesisPillar, Tag("itso_evidence.v1")],
    Discriminator(_projection_version),
]


class MasterSynthesisDetailResponse(BaseModel):
    document_id: UUID
    document_title: str | None = None
    course_code: str | None = None
    course_title: str | None = None
    academic_year: str | None = None
    program: str | None = None
    author: EvaluatorAttribution
    synthesized_score: float | None = None
    adjectival_rating: str | None = None
    evaluation_status: str
    last_updated: datetime | None = None
    pillars: dict[str, MasterPillar]
    flags: list[EvaluationFlagItem] = Field(default_factory=list)
    can_certify: bool


__all__ = [
    "CriterionScoreItem",
    "RawMeasurementItemOut",
    "ReviewerCorrection",
    "DomainScoreBlock",
    "EvaluationFormCriterionPresentation",
    "EvaluationFormDomainPresentation",
    "EvaluationFormPresentation",
    "EvaluationResultsResponse",
    "EvaluationFlagItem",
    "MatrixRowItem",
    "MatrixMetrics",
    "MatrixListResponse",
    "score_to_adjectival",
    "EvaluatorAttribution",
    "MasterSynthesisPillar",
    "MasterSynthesisDetailResponse",
]
