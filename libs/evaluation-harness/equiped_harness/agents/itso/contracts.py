"""Immutable ITSO execution inputs, independent of application storage."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from equiped_harness.runtime.context import AgentExecutionContext, _freeze

if TYPE_CHECKING:
    from equiped_harness.contracts.snapshots import EvaluationFormSnapshotDTO


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
