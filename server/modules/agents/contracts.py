"""Shared contracts for evaluation agents."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class CriterionScore:
    """Structured score for a single rubric criterion."""

    criterion_id: str
    criterion_title: str
    score: int
    justification: str
    chunk_ids: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.score < 1 or self.score > 4:
            raise ValueError("criterion score must be between 1 and 4")


@dataclass(frozen=True, slots=True)
class AgentEvaluationResult:
    """Normalized output produced by a single domain agent."""

    agent_name: str
    evaluation_id: uuid.UUID
    document_id: uuid.UUID
    subtotal: float
    criterion_scores: tuple[CriterionScore, ...]
    summary: str
    model_name: str
    processing_seconds: float
    token_count: int
    prompt_version_id: uuid.UUID | None = None
    success: bool = True
    error_message: str | None = None
    raw_response: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def criterion_count(self) -> int:
        return len(self.criterion_scores)


__all__ = ["AgentEvaluationResult", "CriterionScore"]
