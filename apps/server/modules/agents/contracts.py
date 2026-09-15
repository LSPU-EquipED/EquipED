"""Shared contracts for evaluation agents."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class UngroundedCriterionAdvisory:
    """Advisory entry for an ungrounded criterion."""

    criterion_id: str
    reason: str
    advisory_only: Literal[True] = True

    def __post_init__(self) -> None:
        if not isinstance(self.criterion_id, str):
            raise ValueError("criterion_id must be a string")
        if self.criterion_id != self.criterion_id.strip():
            raise ValueError("criterion_id contains leading or trailing whitespace")
        if not self.criterion_id or len(self.criterion_id) > 50:
            raise ValueError(
                "criterion_id must be non-blank, trimmed, and at most 50 characters"
            )

        if not isinstance(self.reason, str):
            raise ValueError("reason must be a string")
        if self.reason != self.reason.strip():
            raise ValueError("reason contains leading or trailing whitespace")
        if not self.reason or len(self.reason) > 2000:
            raise ValueError(
                "reason must be non-blank, trimmed, and at most 2000 characters"
            )

        if self.advisory_only is not True:
            raise ValueError("advisory_only must be literal True")

    def to_dict(self) -> dict[str, Any]:
        return {
            "criterion_id": self.criterion_id,
            "reason": self.reason,
            "advisory_only": True,
        }

    @classmethod
    def from_dict(cls, data: Any) -> UngroundedCriterionAdvisory:
        if not isinstance(data, dict):
            raise ValueError("data must be a dict")
        if set(data) != {"criterion_id", "reason", "advisory_only"}:
            raise ValueError("exact keys required: criterion_id, reason, advisory_only")
        return cls(
            criterion_id=data["criterion_id"],
            reason=data["reason"],
            advisory_only=data["advisory_only"],
        )


@dataclass(frozen=True, slots=True)
class AdvisoryOutput:
    """Canonical top-level advisory output container."""

    ungrounded_criteria: tuple[UngroundedCriterionAdvisory, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.ungrounded_criteria, tuple):
            raise ValueError("ungrounded_criteria must be a tuple")
        if not (1 <= len(self.ungrounded_criteria) <= 100) or not all(
            isinstance(item, UngroundedCriterionAdvisory)
            for item in self.ungrounded_criteria
        ):
            raise ValueError(
                "ungrounded_criteria must contain between 1 and 100 "
                "UngroundedCriterionAdvisory items"
            )
        cids = [item.criterion_id for item in self.ungrounded_criteria]
        if len(cids) != len(set(cids)):
            raise ValueError("duplicate criterion IDs are rejected")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ungrounded_criteria": [item.to_dict() for item in self.ungrounded_criteria]
        }

    @classmethod
    def from_dict(cls, data: Any) -> AdvisoryOutput:
        if not isinstance(data, dict):
            raise ValueError("data must be a dict")
        if set(data) != {"ungrounded_criteria"}:
            raise ValueError("exact key required: ungrounded_criteria")
        items = data["ungrounded_criteria"]
        if not isinstance(items, list):
            raise ValueError("ungrounded_criteria must be a list")
        return cls(
            ungrounded_criteria=tuple(
                UngroundedCriterionAdvisory.from_dict(item) for item in items
            )
        )


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
    prompt_text: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] | None = None
    advisory_outputs: AdvisoryOutput | None = None

    @property
    def criterion_count(self) -> int:
        return len(self.criterion_scores)


__all__ = [
    "AdvisoryOutput",
    "AgentEvaluationResult",
    "CriterionScore",
    "UngroundedCriterionAdvisory",
]
