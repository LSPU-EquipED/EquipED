"""Pydantic schemas for criterion-level feedback."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class CriterionFeedbackCreate(BaseModel):
    """Request body for POST /feedback/{evaluation_id}/criteria/{criterion_id}.

    ``agent_name`` is restricted to agents whose score+justification come
    from a single LLM generation and can therefore produce a coherent DPO
    pair: "itso" (one call scores all 5 criteria) and "sme" (3 grouped
    calls score all 10 criteria -- see
    docs/superpowers/specs/2026-08-13-sme-dpo-scoring-design.md).
    Coordinator and GAD are not included: Coordinator's non-A-05 scores
    are copied from SME (corrections against those belong to "sme"), and
    GAD's score is still code-computed from extracted facts.
    """

    agent_name: Literal["itso", "sme"]
    action: Literal["ACCEPT", "REJECT", "EDIT"]
    score: int | None = Field(default=None, ge=1, le=4)
    justification: str | None = Field(default=None, min_length=1, max_length=2000)
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _edit_requires_score_and_justification(self) -> CriterionFeedbackCreate:
        if self.action == "EDIT" and (self.score is None or not self.justification):
            raise ValueError(
                "EDIT actions require both 'score' and 'justification' so the "
                "correction is internally consistent."
            )
        return self


class CriterionFeedbackResponse(BaseModel):
    log_id: uuid.UUID
    evaluation_id: uuid.UUID
    user_id: uuid.UUID
    agent_name: str | None
    criterion_id: str | None
    action: Literal["ACCEPT", "REJECT", "EDIT"]
    edited_json: dict | None = None
    notes: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


__all__ = ["CriterionFeedbackCreate", "CriterionFeedbackResponse"]
