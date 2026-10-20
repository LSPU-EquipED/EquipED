"""Portable contracts for locally prepared reference and policy evidence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class PolicyRetrievalPlan:
    """Agent-owned policy retrieval instructions consumed by local adapters."""

    agent_id: str
    adapter_version: int
    criteria_areas: Mapping[str, tuple[str, ...]]
    query_text: str
    retrieval_version: str = "1"
    max_chunks: int = 5

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "criteria_areas",
            MappingProxyType(
                {
                    criterion: tuple(areas)
                    for criterion, areas in self.criteria_areas.items()
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class PolicyEvidenceChunk:
    """A policy clause retrieved by the local data adapter."""

    chunk_id: str
    document_id: str
    text: str
    policy_area: str
    page_number: int | None
    token_count: int | None
    distance: float


@dataclass(frozen=True, slots=True)
class PolicyRetrievalResult:
    """Bounded retrieval outcome for one policy criterion."""

    policy_area: str
    status: Literal["available", "unavailable"]
    chunks: tuple[PolicyEvidenceChunk, ...]
    provenance_hash: str

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)


@dataclass(frozen=True, slots=True)
class PolicyEvidenceSnapshot:
    """Immutable policy evidence and provenance prepared for one evaluation."""

    provenance: Mapping[str, Any] | None
    policy_evidence: Mapping[str, Any] | None


__all__ = [
    "PolicyEvidenceChunk",
    "PolicyEvidenceSnapshot",
    "PolicyRetrievalPlan",
    "PolicyRetrievalResult",
]
