"""Pydantic schemas for criterion-level feedback."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ValidAgentName = Literal["sme", "coordinator", "gad", "itso"]

# Item-level corrections (toggling a single extracted instance/qualifying
# unit) are only meaningful for agents whose score is code-computed from a
# list of LLM-extracted items -- SME and Coordinator today. See
# server/modules/agents/envelope_map.py for why these two specifically.
ITEM_LEVEL_AGENTS = ("sme", "coordinator")

FeedbackAction = Literal["ACCEPT", "REJECT", "EDIT", "ITEM_REJECT", "ITEM_ACCEPT"]
_ITEM_LEVEL_ACTIONS = ("ITEM_REJECT", "ITEM_ACCEPT")


class CriterionFeedbackCreate(BaseModel):
    """Request body for POST /feedback/{evaluation_id}/criteria/{criterion_id}."""

    agent_name: ValidAgentName
    action: FeedbackAction
    score: int | None = Field(default=None, ge=1, le=4)
    justification: str | None = Field(default=None, min_length=1, max_length=2000)
    notes: str | None = Field(default=None, max_length=2000)
    item_id: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def _edit_requires_score_and_justification(self) -> CriterionFeedbackCreate:
        if self.action == "EDIT":
            if self.score is None or not self.justification:
                raise ValueError(
                    "EDIT actions require both 'score' and 'justification' so the "
                    "correction is internally consistent."
                )
        elif self.action in _ITEM_LEVEL_ACTIONS:
            if self.score is not None or self.justification is not None:
                raise ValueError(
                    f"{self.action} actions forbid 'score' and 'justification'; "
                    "they target one extracted item, not the criterion score."
                )
        else:
            if self.score is not None:
                raise ValueError(
                    f"{self.action} actions forbid 'score'; "
                    "only EDIT may carry a corrected score."
                )

        if self.action in _ITEM_LEVEL_ACTIONS:
            if self.item_id is None:
                raise ValueError(f"{self.action} actions require 'item_id'")
            if self.agent_name not in ITEM_LEVEL_AGENTS:
                raise ValueError(
                    f"{self.action} actions are only supported for agents "
                    f"{ITEM_LEVEL_AGENTS}, got '{self.agent_name}'"
                )
        elif self.item_id is not None:
            raise ValueError(f"{self.action} actions forbid 'item_id'")
        return self


class CriterionFeedbackResponse(BaseModel):
    log_id: uuid.UUID
    evaluation_id: uuid.UUID
    user_id: uuid.UUID
    agent_name: str | None
    criterion_id: str | None
    item_id: str | None = None
    action: FeedbackAction
    edited_json: dict | None = None
    notes: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


__all__ = [
    "CriterionFeedbackCreate",
    "CriterionFeedbackResponse",
    "FeedbackAction",
    "ITEM_LEVEL_AGENTS",
    "ValidAgentName",
]
