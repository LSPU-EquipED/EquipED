"""Focused concurrency and snapshot tests for supervisor Phase 1."""

from __future__ import annotations

from concurrent.futures import Future
from dataclasses import dataclass
from threading import Barrier
from types import MappingProxyType
from uuid import uuid4

import pytest
from server.modules.agents.contracts import AgentEvaluationResult
from server.modules.agents.itso.evidence import ITSOEvidenceSnapshot
from server.modules.agents.supervision.context import (
    EvaluationContextBuilder,
    PreparedEvaluationContext,
    PromptSnapshot,
)
from server.modules.agents.supervision.dispatch import AgentDispatcher
from server.modules.agents.supervision.supervisor import Supervisor


def _context() -> PreparedEvaluationContext:
    return PreparedEvaluationContext(
        chunk_infos=(
            MappingProxyType({"chunk_id": "c1", "text": "original", "tags": ("a",)}),
        ),
        query_text="query",
        prompt_versions=MappingProxyType({"a": PromptSnapshot(1, "prompt")}),
        reference_document_ids=MappingProxyType({"syllabus": "ref-1"}),
        precomputed_context=MappingProxyType({"syllabus": ("reference",)}),
        canonical_source_text="canonical source",
        authoritative_curriculum_text=None,
    )


def test_prepared_context_rejects_nested_mutation_and_preserves_values() -> None:
    prepared = _context()
    with pytest.raises(TypeError):
        prepared.chunk_infos[0]["text"] = "changed"
    with pytest.raises(TypeError):
        prepared.chunk_infos[0]["tags"][0] = "b"
    with pytest.raises(TypeError):
        prepared.precomputed_context["syllabus"] += ("changed",)
    with pytest.raises(TypeError):
        prepared.reference_document_ids["syllabus"] = "changed"
    assert prepared == _context()


@dataclass
class _Agent:
    agent_name: str
    seen: list[object]

    def run(self, **kwargs):
        chunks = kwargs["chunk_infos"]
        chunks[0]["text"] = self.agent_name
        chunks[0]["tags"].append(self.agent_name)
        kwargs["precomputed_context"]["syllabus"].append(self.agent_name)
        kwargs["reference_document_ids"]["syllabus"] = self.agent_name
        self.seen.append((chunks, kwargs["precomputed_context"]))
        return _result(self.agent_name, kwargs["evaluation_id"], kwargs["document_id"])


def _result(name, evaluation_id, document_id, *, success=True):
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
        prompt_version_id=1,
        success=success,
    )


def _dispatch(monkeypatch, agents, prepared):
    return AgentDispatcher(agents).dispatch(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=prepared.chunk_infos,
        context_text=prepared.query_text,
        prompt_versions=MappingProxyType(
            {a.agent_name: PromptSnapshot(1, "prompt") for a in agents}
        ),
        reference_document_ids=prepared.reference_document_ids,
        precomputed_context=prepared.precomputed_context,
        provenance=None,
        policy_evidence=None,
        roadmap_context=None,
    )


def test_dispatched_agents_receive_independent_mutable_snapshots(monkeypatch) -> None:
    prepared = _context()
    a, b = _Agent("a", []), _Agent("b", [])
    _dispatch(monkeypatch, [a, b], prepared)
    assert b.seen[0][0][0]["text"] == "b"
    assert prepared.chunk_infos[0]["text"] == "original"
    assert prepared.precomputed_context["syllabus"] == ("reference",)
    assert prepared.reference_document_ids["syllabus"] == "ref-1"


def test_supervisor_builds_context_and_evidence_before_dispatch(monkeypatch) -> None:
    events = []
    prepared = PreparedEvaluationContext(
        chunk_infos=_context().chunk_infos,
        query_text="query",
        prompt_versions=MappingProxyType({"itso": PromptSnapshot(1, "prompt")}),
        reference_document_ids=MappingProxyType({}),
        precomputed_context=MappingProxyType({}),
        canonical_source_text="canonical source",
        authoritative_curriculum_text=None,
    )
    evidence = ITSOEvidenceSnapshot(
        MappingProxyType({"p": 1}), MappingProxyType({"e": 2})
    )
    monkeypatch.setattr(
        EvaluationContextBuilder,
        "build",
        lambda *a, **k: events.append("context") or prepared,
    )
    monkeypatch.setattr(
        "server.modules.agents.supervision.supervisor.ITSOEvidenceBuilder.build",
        lambda self, chunks: events.append("evidence") or evidence,
    )

    def dispatch(self, **kwargs):
        events.append(
            (
                "dispatch",
                isinstance(kwargs["prompt_versions"]["itso"], PromptSnapshot),
                kwargs["provenance"],
            )
        )
        return [_result("itso", kwargs["evaluation_id"], kwargs["document_id"])], {}

    monkeypatch.setattr(AgentDispatcher, "dispatch", dispatch)
    result = Supervisor(agents=[_Agent("itso", [])]).run_evaluation(
        evaluation_id=uuid4(), document_id=uuid4(), chunks=[object()]
    )
    assert result.agent_results
    assert events == ["context", "evidence", ("dispatch", True, evidence.provenance)]


def test_dispatch_submits_once_and_creates_one_client_per_agent(monkeypatch) -> None:
    agents = [_Agent(name, []) for name in ("a", "b", "c")]
    submitted, clients = [], []
    monkeypatch.setattr(
        "server.modules.agents.supervision.dispatch.get_llm_client_for_agent",
        lambda name: clients.append(name) or object(),
    )
    import server.modules.agents.supervision.dispatch as module

    class Executor:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def submit(self, fn, **kwargs):
            submitted.append(kwargs["agent_name"])
            future = Future()
            future.set_result(fn(**kwargs))
            return future

    monkeypatch.setattr(module.concurrent.futures, "ThreadPoolExecutor", Executor)
    _dispatch(monkeypatch, agents, _context())
    assert submitted == ["a", "b", "c"] and clients == submitted


def test_dispatch_agents_overlap_with_real_thread_pool(monkeypatch) -> None:
    barrier = Barrier(2)

    class Agent(_Agent):
        def run(self, **kwargs):
            barrier.wait(timeout=2)
            return super().run(**kwargs)

    results, failures = _dispatch(
        monkeypatch, [Agent("a", []), Agent("b", [])], _context()
    )
    assert {r.agent_name for r in results} == {"a", "b"} and not failures


def test_client_factory_failure_isolated_and_other_agent_succeeds(monkeypatch) -> None:
    attempts = []

    def factory(name):
        attempts.append(name)
        if name == "a":
            raise RuntimeError("factory failed")
        return object()

    monkeypatch.setattr(
        "server.modules.agents.supervision.dispatch.get_llm_client_for_agent", factory
    )
    results, failures = _dispatch(
        monkeypatch, [_Agent("a", []), _Agent("b", [])], _context()
    )
    assert set(attempts) == {"a", "b"}
    assert {r.agent_name for r in results} == {"a", "b"}
    assert failures["a"].startswith("RuntimeError") and not failures.get("b")
