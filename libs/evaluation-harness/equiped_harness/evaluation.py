"""Public prepared-input evaluation seam. No queue or transport ownership."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields
from typing import Any
from uuid import UUID

from .config import ExecutionConfig, execution_scope
from .coordinator import Coordinator
from .gad import GAD
from .itso import ITSO
from .result_contracts import AgentEvaluationResult
from .runtime.context import _freeze, thaw
from .sme import SME
from .snapshot_contracts import EvaluationFormSnapshotDTO
from .transport import ModelClient

SPECIALIST_CLASSES = (SME, Coordinator, GAD, ITSO)
_EVALUATORS = {cls.agent_name: cls for cls in SPECIALIST_CLASSES}


@dataclass(frozen=True, slots=True)
class EvaluationRequest:
    evaluation_id: UUID
    document_id: UUID
    form_snapshot: EvaluationFormSnapshotDTO
    chunk_infos: tuple[Mapping[str, Any], ...]
    context_text: str | None = None
    reference_text: str | None = None
    prompt_version: str | None = None
    prompt_version_id: UUID | None = None
    canonical_source_text: str | None = None
    curriculum_id: UUID | None = None
    curriculum_context: str | None = None
    reference_document_ids: Mapping[str, Any] | None = None
    precomputed_context: Mapping[str, Any] | None = None
    provenance: Mapping[str, Any] | None = None
    policy_evidence: Mapping[str, Any] | None = None
    roadmap_context: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.form_snapshot, EvaluationFormSnapshotDTO):
            raise TypeError("form_snapshot must be EvaluationFormSnapshotDTO")
        for name in (
            "chunk_infos",
            "reference_document_ids",
            "precomputed_context",
            "provenance",
            "policy_evidence",
            "roadmap_context",
        ):
            object.__setattr__(self, name, _freeze(getattr(self, name)))


def evaluate(
    request: EvaluationRequest, client: ModelClient, config: ExecutionConfig
) -> AgentEvaluationResult:
    """Evaluate a prepared snapshot with explicitly supplied transport/config."""
    if not isinstance(request, EvaluationRequest):
        raise TypeError("request must be EvaluationRequest")
    if client is None:
        raise TypeError("client must be explicitly supplied")
    if (
        request.form_snapshot.agent_id == "itso"
        and request.form_snapshot.adapter_version != 3
    ):
        raise ValueError(
            f"Unsupported ITSO adapter version {request.form_snapshot.adapter_version}"
        )
    cls = _EVALUATORS.get(request.form_snapshot.agent_id)
    if cls is None:
        raise ValueError("Unsupported specialist")
    kwargs = {
        field.name: thaw(getattr(request, field.name)) for field in fields(request)
    }
    with execution_scope(config):
        return cls().run(**kwargs, llm_client=client)
