"""Pydantic schemas for criterion-level feedback."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ValidAgentName = Literal["sme", "coordinator", "gad", "itso"]


class CriterionFeedbackCreate(BaseModel):
    """Request body for POST /feedback/{evaluation_id}/criteria/{criterion_id}."""

    agent_name: ValidAgentName
    action: Literal["ACCEPT", "REJECT", "EDIT"]
    score: int | None = Field(default=None, ge=1, le=4)
    justification: str | None = Field(default=None, min_length=1, max_length=2000)
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _edit_requires_score_and_justification(self) -> CriterionFeedbackCreate:
        if self.action == "EDIT":
            if self.score is None or not self.justification:
                raise ValueError(
                    "EDIT actions require both 'score' and 'justification' so the "
                    "correction is internally consistent."
                )
        else:
            if self.score is not None:
                raise ValueError(
                    f"{self.action} actions forbid 'score'; "
                    "only EDIT may carry a corrected score."
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

    model_config = ConfigDict(from_attributes=True)


__all__ = ["CriterionFeedbackCreate", "CriterionFeedbackResponse", "ValidAgentName"]
