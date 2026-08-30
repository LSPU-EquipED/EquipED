"""Immutable request-scoped contracts shared by agent runtime code."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from server.modules.rubrics.snapshot_contracts import EvaluationFormSnapshotDTO


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, set):
        return frozenset(_freeze(v) for v in value)
    return value


def thaw(value: Any) -> Any:
    """Return mutable JSON-compatible copies at the serialization boundary."""
    if isinstance(value, Mapping):
        return {key: thaw(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [thaw(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return [thaw(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class AgentExecutionContext:
    evaluation_id: UUID
    document_id: UUID
    chunk_infos: tuple[Mapping[str, Any], ...] = ()
    context_text: str | None = None
    reference_text: str | None = None
    prompt_version: str | None = None
    prompt_version_id: UUID | None = None
    provenance: Mapping[str, Any] = None  # type: ignore[assignment]
    domain_keywords: tuple[str, ...] = ()
    reference_document_ids: Mapping[str, Any] = None  # type: ignore[assignment]
    precomputed_context: Mapping[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "chunk_infos", tuple(_freeze(c) for c in self.chunk_infos)
        )
        object.__setattr__(self, "provenance", _freeze(self.provenance or {}))
        object.__setattr__(
            self, "reference_document_ids", _freeze(self.reference_document_ids or {})
        )
        object.__setattr__(
            self, "precomputed_context", _freeze(self.precomputed_context or {})
        )


@dataclass(frozen=True, slots=True)
class ITSOExecutionContext(AgentExecutionContext):
    policy_evidence: Mapping[str, Any] = None  # type: ignore[assignment]
    form_snapshot: EvaluationFormSnapshotDTO | None = None
    llm_client: Any | None = None
    llm_temperature: float | None = None
    domain_keywords: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        AgentExecutionContext.__post_init__(self)
        object.__setattr__(self, "policy_evidence", _freeze(self.policy_evidence or {}))
