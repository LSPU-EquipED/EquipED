"""Coordinator client isolation and safe failure logging tests."""

from __future__ import annotations

import json
import threading
import uuid

from server.modules.agents.contracts import AgentEvaluationResult, CriterionScore
from server.modules.agents.coordinator import curriculum, reconciliation, summary
from server.modules.agents.coordinator.agent import Coordinator

from .test_coordinator_run import _BASKET_A1, _CHUNK_INFOS, _make_agent


class _BarrierClient:
    def __init__(self, barrier: threading.Barrier, model: str) -> None:
        self.barrier = barrier
        self.model = model
        self.calls = 0

    def generate(self, prompt: str, **_: object) -> str:
        self.calls += 1
        self.barrier.wait(timeout=5)
        return json.dumps(_BASKET_A1)


def test_same_coordinator_instance_does_not_mutate_default_client(
    monkeypatch,
) -> None:
    barrier = threading.Barrier(2)
    first = _BarrierClient(barrier, "first-model")
    second = _BarrierClient(barrier, "second-model")
    default = object()
    agent = _make_agent(monkeypatch, default)
    results: list[AgentEvaluationResult] = []

    def run(client: _BarrierClient) -> None:
        results.append(
            agent.run(
                evaluation_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                chunk_infos=_CHUNK_INFOS,
                context_text="full text",
                llm_client=client,
            )
        )

    threads = [
        threading.Thread(target=run, args=(client,)) for client in (first, second)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert all(not thread.is_alive() for thread in threads)
    assert first.calls == second.calls == 1
    assert {result.model_name for result in results} == {"first-model", "second-model"}
    assert agent._default_llm_client is default


def test_independent_forwards_supplied_client_and_keeps_instance_unchanged(
    monkeypatch,
) -> None:
    supplied = object()
    default = object()
    agent = Coordinator(llm_client=default)
    captured: dict[str, object] = {}
    score = CriterionScore("A-05", "A-05", 3, "alignment")
    result = AgentEvaluationResult(
        agent_name="coordinator",
        evaluation_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        subtotal=3,
        criterion_scores=(score,),
        summary="old",
        model_name="model",
        processing_seconds=0,
        token_count=1,
        success=True,
    )

    def fake_engine(**kwargs):
        captured.update(kwargs)
        return result

    monkeypatch.setattr(agent, "_run_full_engine_scoring", fake_engine)

    def fake_summary(scores, client):
        captured["summary_client"] = client
        return "summary"

    monkeypatch.setattr(reconciliation, "_build_llm_alignment_summary", fake_summary)
    output = reconciliation.run_full_independent(
        agent,
        evaluation_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_infos=_CHUNK_INFOS,
        context_text="text",
        llm_client=supplied,
    )

    assert captured["llm_client"].primary_client is supplied
    assert captured["summary_client"] is captured["llm_client"]
    assert output.summary == "summary"
    assert agent._default_llm_client is default


def test_retrieval_and_summary_logs_do_not_expose_exception(
    caplog, monkeypatch
) -> None:
    secret = "TOP-SECRET-CURRICULUM"
    client = type(
        "Client",
        (),
        {"generate": lambda *_args, **_kwargs: json.dumps(_BASKET_A1)},
    )()
    agent = _make_agent(monkeypatch, client)
    monkeypatch.setattr(
        curriculum,
        "prepare_curriculum_text",
        lambda *args: (_ for _ in ()).throw(RuntimeError(secret)),
    )
    with caplog.at_level("WARNING"):
        agent.run(
            evaluation_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            chunk_infos=_CHUNK_INFOS,
            context_text="text",
            reference_document_ids={"curriculum": uuid.uuid4()},
        )
        failing_client = type(
            "FailingClient",
            (),
            {
                "generate": lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    ValueError(secret)
                )
            },
        )()
        summary._build_llm_alignment_summary(
            (CriterionScore("A-05", "A-05", 3, "x"),), failing_client
        )
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert secret not in messages
    assert "RuntimeError" in messages and "AgentLLMError" in messages
    references = [
        record.getMessage().split("reference=")[1].split(")")[0]
        for record in caplog.records
        if "reference=" in record.getMessage()
    ]
    assert references and all(len(reference) == 16 for reference in references)
