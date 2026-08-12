from __future__ import annotations

from threading import Event, get_ident
from types import MappingProxyType
from uuid import uuid4

import pytest
from server.modules.agents.contracts import AgentEvaluationResult
from server.modules.agents.exceptions import SupervisorExecutionError
from server.modules.agents.supervision import dispatch
from server.modules.agents.supervision.context import (
    EvaluationContextBuilder,
    PromptSnapshot,
)


def _result(name, evaluation_id, document_id, prompt_id):
    return AgentEvaluationResult(
        agent_name=name,
        evaluation_id=evaluation_id,
        document_id=document_id,
        subtotal=1,
        criterion_scores=(),
        summary="ok",
        model_name="test",
        processing_seconds=0,
        token_count=0,
        prompt_version_id=prompt_id,
    )


class _Agent:
    def __init__(self, name, started=None, gate=None):
        self.agent_name, self.started, self.gate = name, started, gate
        self.seen = None

    def run(self, **kwargs):
        self.seen = kwargs
        if self.started:
            self.started.set()
            (self.gate or self.started).wait(2)
        return _result(
            self.agent_name,
            kwargs["evaluation_id"],
            kwargs["document_id"],
            kwargs["prompt_version_id"],
        )


def _dispatch(monkeypatch, agents, heartbeat_callback=None):
    monkeypatch.setattr(dispatch, "get_llm_client_for_agent", lambda _: object())
    prompts = MappingProxyType(
        {a.agent_name: PromptSnapshot(1, "prompt") for a in agents}
    )
    return dispatch.AgentDispatcher(agents).dispatch(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=(),
        context_text="q",
        prompt_versions=prompts,
        reference_document_ids=MappingProxyType({}),
        precomputed_context=MappingProxyType({}),
        provenance=None,
        policy_evidence=None,
        roadmap_context=None,
        canonical_source_text="canonical",
        heartbeat_callback=heartbeat_callback,
    )


def test_canonical_source_only_reaches_sme_and_coordinator(monkeypatch):
    agents = [_Agent(name) for name in ("sme", "coordinator", "gad", "itso")]
    _dispatch(monkeypatch, agents)
    assert (
        agents[0].seen["canonical_source_text"]
        == agents[1].seen["canonical_source_text"]
        == "canonical"
    )
    assert "canonical_source_text" not in agents[2].seen
    assert "canonical_source_text" not in agents[3].seen


def test_canonical_preparation_failure_submits_zero_futures(monkeypatch):
    submitted = []
    monkeypatch.setattr(
        EvaluationContextBuilder,
        "_load_active_prompt_versions",
        lambda self: MappingProxyType({}),
    )
    monkeypatch.setattr(
        "server.modules.agents.supervision.context.prepare_canonical_source",
        lambda _: (_ for _ in ()).throw(OSError()),
    )
    builder = EvaluationContextBuilder(None, [])
    with pytest.raises(SupervisorExecutionError):
        builder.build(
            chunks=[
                type(
                    "Chunk", (), {"chunk_id": uuid4(), "page_number": 1, "text": "x"}
                )()
            ],
            query_text=None,
            context={"document_id": uuid4()},
        )
    assert submitted == []


def test_heartbeat_repeats_on_dispatch_owner_thread(monkeypatch):
    gate = Event()
    started = Event()
    calls = []
    monkeypatch.setattr(dispatch.AgentDispatcher, "HEARTBEAT_INTERVAL_SECONDS", 0.01)

    def heartbeat():
        calls.append(get_ident())
        if len(calls) >= 3:
            gate.set()

    result = _dispatch(monkeypatch, [_Agent("sme", started, gate)], heartbeat)
    assert result[0] and len(calls) >= 2 and len(set(calls)) == 1


def test_heartbeat_failure_returns_no_results(monkeypatch):
    started = Event()
    monkeypatch.setattr(dispatch.AgentDispatcher, "HEARTBEAT_INTERVAL_SECONDS", 0.01)
    with pytest.raises(SupervisorExecutionError):
        _dispatch(
            monkeypatch,
            [_Agent("sme", started)],
            lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        )
