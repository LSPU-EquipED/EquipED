"""Public prepared-input evaluation seam. No queue or transport ownership."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields
from typing import Any
from uuid import UUID

from equiped_harness.contracts.results import AgentEvaluationResult
from equiped_harness.contracts.snapshots import (
    EvaluationFormSnapshotDTO,
    SnapshotIntegrityError,
    verify_evaluation_form_snapshot,
)
from equiped_harness.registry import get_agent_class
from equiped_harness.runtime.config import ExecutionConfig, execution_scope
from equiped_harness.runtime.context import _freeze, thaw
from equiped_harness.runtime.control import ExecutionControl
from equiped_harness.runtime.model import ModelClient
from equiped_harness.tools.config import ToolConfig


class _ControlledModelClient:
    def __init__(self, client: ModelClient, control: ExecutionControl) -> None:
        self._client = client
        self._control = control
        self.model = getattr(client, "model", "unknown")

    def __getattr__(self, name: str):
        return getattr(self._client, name)

    def generate_result(self, *args, **kwargs):
        self._control.check()
        return self._client.generate_result(*args, **kwargs)


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
    request: EvaluationRequest,
    client: ModelClient,
    config: ExecutionConfig,
    *,
    tools: ToolConfig | None = None,
    control: ExecutionControl | None = None,
) -> AgentEvaluationResult:
    """Evaluate a prepared snapshot with explicitly supplied transport/config."""
    if not isinstance(request, EvaluationRequest):
        raise TypeError("request must be EvaluationRequest")
    if client is None:
        raise TypeError("client must be explicitly supplied")
    if not isinstance(config, ExecutionConfig):
        raise TypeError("config must be ExecutionConfig")
    if tools is not None and not isinstance(tools, ToolConfig):
        raise TypeError("tools must be ToolConfig")
    if control is not None and not isinstance(control, ExecutionControl):
        raise TypeError("control must be ExecutionControl")
    control = control or ExecutionControl()
    control.check()
    snapshot = request.form_snapshot
    if request.evaluation_id != snapshot.evaluation_id:
        raise SnapshotIntegrityError(
            "evaluation_id mismatch between request and form snapshot"
        )
    verify_evaluation_form_snapshot(
        snapshot_id=snapshot.snapshot_id,
        evaluation_id=snapshot.evaluation_id,
        agent_id=snapshot.agent_id,
        rubric_set_id=snapshot.rubric_set_id,
        adapter_key=snapshot.adapter_key,
        adapter_version=snapshot.adapter_version,
        snapshot_hash=snapshot.snapshot_hash,
        snapshot_payload=snapshot.snapshot_payload.model_dump(mode="json"),
    )
    cls = get_agent_class(request.form_snapshot.agent_id)
    kwargs = {
        field.name: thaw(getattr(request, field.name)) for field in fields(request)
    }
    model_client = _ControlledModelClient(client, control)
    with execution_scope(config):
        control.check()
        agent = cls()
        prepare_inputs = getattr(agent, "prepare_inputs", None)
        if prepare_inputs is not None:
            kwargs = prepare_inputs(kwargs, tools=tools, control=control)
        control.check()
        result = agent.run(**kwargs, llm_client=model_client)
        control.check()
        return result
