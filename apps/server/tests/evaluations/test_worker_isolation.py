"""Tests for Phase-3 worker form-snapshot transport and fail-closed validation."""

from __future__ import annotations

import uuid
from types import MappingProxyType
from unittest.mock import MagicMock

import pytest
from server.modules.agents.contracts import AgentEvaluationResult
from server.modules.agents.exceptions import SupervisorExecutionError
from server.modules.agents.supervision import dispatch
from server.modules.agents.supervision.context import PromptSnapshot
from server.modules.rubrics.snapshot_contracts import EvaluationFormSnapshotDTO
from server.tests.agents.helpers import _make_dummy_snapshot


class _MockWorkerAgent:
    def __init__(self, name: str) -> None:
        self.agent_name = name
        self.received_snapshot = None
        self.received_kwargs = None

    def run(self, **kwargs) -> AgentEvaluationResult:
        self.received_snapshot = kwargs.get("form_snapshot")
        self.received_kwargs = kwargs
        return AgentEvaluationResult(
            agent_name=self.agent_name,
            evaluation_id=kwargs["evaluation_id"],
            document_id=kwargs["document_id"],
            subtotal=3.0,
            criterion_scores=(),
            summary="ok",
            model_name="test-model",
            processing_seconds=0.01,
            token_count=10,
            prompt_version_id=kwargs.get("prompt_version_id"),
            success=True,
        )


def _dispatch_helper(
    monkeypatch,
    agents: list[object],
    form_snapshots: tuple[EvaluationFormSnapshotDTO, ...],
    evaluation_id: uuid.UUID | None = None,
):
    monkeypatch.setattr(dispatch, "get_llm_client_for_agent", lambda _: object())
    eval_id = evaluation_id or uuid.uuid4()
    prompts = MappingProxyType(
        {getattr(a, "agent_name"): PromptSnapshot(1, "prompt") for a in agents}
    )
    return dispatch.AgentDispatcher(agents).dispatch(
        evaluation_id=eval_id,
        document_id=uuid.uuid4(),
        chunk_infos=(),
        form_snapshots=form_snapshots,
        context_text="q",
        prompt_versions=prompts,
        reference_document_ids=MappingProxyType({}),
        precomputed_context=MappingProxyType({}),
        provenance=None,
        policy_evidence=None,
        roadmap_context=None,
    )


def test_exact_frozen_snapshot_reaches_correct_worker(monkeypatch) -> None:
    eval_id = uuid.uuid4()
    sme_agent = _MockWorkerAgent("sme")
    gad_agent = _MockWorkerAgent("gad")
    agents = [sme_agent, gad_agent]

    sme_snap = _make_dummy_snapshot("sme", eval_id)
    gad_snap = _make_dummy_snapshot("gad", eval_id)
    snapshots = (sme_snap, gad_snap)

    results, failures = _dispatch_helper(
        monkeypatch, agents, snapshots, evaluation_id=eval_id
    )
    assert not failures
    assert len(results) == 2
    # Verify exact frozen instance reaches the worker (identity check)
    assert sme_agent.received_snapshot is not None
    assert sme_agent.received_snapshot is sme_snap
    assert sme_agent.received_snapshot.agent_id == "sme"
    assert sme_agent.received_snapshot.snapshot_hash == sme_snap.snapshot_hash
    assert gad_agent.received_snapshot is not None
    assert gad_agent.received_snapshot is gad_snap
    assert gad_agent.received_snapshot.agent_id == "gad"
    assert gad_agent.received_snapshot.snapshot_hash == gad_snap.snapshot_hash

    # Verify workers do not receive a db session
    assert "db" not in sme_agent.received_kwargs
    assert "session" not in sme_agent.received_kwargs
    assert "db" not in gad_agent.received_kwargs
    assert "session" not in gad_agent.received_kwargs


def test_duplicate_worker_agent_names_fails_closed(monkeypatch) -> None:
    eval_id = uuid.uuid4()
    agents = [_MockWorkerAgent("sme"), _MockWorkerAgent("sme")]
    snapshots = (_make_dummy_snapshot("sme", eval_id),)
    with pytest.raises(SupervisorExecutionError) as exc_info:
        _dispatch_helper(monkeypatch, agents, snapshots, evaluation_id=eval_id)
    assert "Duplicate worker agent names" in str(exc_info.value)


def test_duplicate_snapshot_agent_ids_fails_closed(monkeypatch) -> None:
    eval_id = uuid.uuid4()
    agents = [_MockWorkerAgent("sme")]
    snap1 = _make_dummy_snapshot("sme", eval_id)
    snap2 = _make_dummy_snapshot("sme", eval_id)
    snapshots = (snap1, snap2)
    with pytest.raises(SupervisorExecutionError) as exc_info:
        _dispatch_helper(monkeypatch, agents, snapshots, evaluation_id=eval_id)
    assert "Duplicate agent_id found in form_snapshots" in str(exc_info.value)


def test_missing_worker_in_snapshots_fails_closed(monkeypatch) -> None:
    eval_id = uuid.uuid4()
    agents = [_MockWorkerAgent("sme"), _MockWorkerAgent("gad")]
    snapshots = (_make_dummy_snapshot("sme", eval_id),)
    with pytest.raises(SupervisorExecutionError) as exc_info:
        _dispatch_helper(monkeypatch, agents, snapshots, evaluation_id=eval_id)
    assert "Snapshot agent-id set does not match" in str(exc_info.value)


def test_extra_snapshot_fails_closed(monkeypatch) -> None:
    eval_id = uuid.uuid4()
    agents = [_MockWorkerAgent("sme")]
    snapshots = (
        _make_dummy_snapshot("sme", eval_id),
        _make_dummy_snapshot("gad", eval_id),
    )
    with pytest.raises(SupervisorExecutionError) as exc_info:
        _dispatch_helper(monkeypatch, agents, snapshots, evaluation_id=eval_id)
    assert "Snapshot agent-id set does not match" in str(exc_info.value)


def test_snapshot_evaluation_id_mismatch_fails_closed(monkeypatch) -> None:
    eval_id = uuid.uuid4()
    other_eval_id = uuid.uuid4()
    agents = [_MockWorkerAgent("sme")]
    snapshots = (_make_dummy_snapshot("sme", other_eval_id),)
    with pytest.raises(SupervisorExecutionError) as exc_info:
        _dispatch_helper(monkeypatch, agents, snapshots, evaluation_id=eval_id)
    assert "evaluation_id does not match" in str(exc_info.value)


def test_tampered_snapshot_hash_fails_closed_before_execution(monkeypatch) -> None:
    eval_id = uuid.uuid4()
    client_factory_mock = MagicMock()
    monkeypatch.setattr(dispatch, "get_llm_client_for_agent", client_factory_mock)
    agents = [_MockWorkerAgent("sme")]
    snap = _make_dummy_snapshot("sme", eval_id)

    # Tamper with snapshot DTO hash
    tampered_snap = EvaluationFormSnapshotDTO.model_construct(
        snapshot_id=snap.snapshot_id,
        evaluation_id=snap.evaluation_id,
        agent_id=snap.agent_id,
        rubric_set_id=snap.rubric_set_id,
        adapter_key=snap.adapter_key,
        adapter_version=snap.adapter_version,
        snapshot_payload=snap.snapshot_payload,
        snapshot_hash="0" * 64,
    )

    with pytest.raises(SupervisorExecutionError) as exc_info:
        _dispatch_helper(monkeypatch, agents, (tampered_snap,), evaluation_id=eval_id)
    assert "Form snapshot failed dispatch integrity re-verification" in str(
        exc_info.value
    )
    # Check that LLM client was never resolved
    client_factory_mock.assert_not_called()


def test_non_dto_item_in_snapshots_fails_closed(monkeypatch) -> None:
    eval_id = uuid.uuid4()
    agents = [_MockWorkerAgent("sme")]
    with pytest.raises(SupervisorExecutionError) as exc_info:
        _dispatch_helper(
            monkeypatch,
            agents,
            ("not_a_dto",),  # type: ignore[arg-type]
            evaluation_id=eval_id,
        )
    assert "form_snapshots must be a tuple of EvaluationFormSnapshotDTO" in str(
        exc_info.value
    )
