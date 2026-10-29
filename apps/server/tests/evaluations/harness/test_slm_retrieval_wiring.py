"""Backend preparation and dispatch for Coordinator SLM retrieval."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from equiped_harness import EvaluationRequest
from equiped_harness.contracts.results import AgentEvaluationResult
from equiped_harness.contracts.snapshots import build_evaluation_form_snapshot
from equiped_harness.exceptions import SupervisorExecutionError
from equiped_harness.registry import get_agent_class
from server.modules.evaluations.context import EvaluationContextBuilder
from server.modules.evaluations.dispatch import AgentDispatcher
from server.tests.agents.helpers import _make_dummy_snapshot


def _coord_snapshot(version=4, evaluation_id=None):
    base = _make_dummy_snapshot("coordinator", evaluation_id)
    return build_evaluation_form_snapshot(
        base.evaluation_id,
        base.form.model_copy(update={"adapter_version": version}),
    )


def _builder(monkeypatch, *, source_type="slm", agent_name="coordinator"):
    document_id = uuid4()
    document = SimpleNamespace(
        document_id=document_id,
        file_path="/tmp/slm.pdf",
        source_type=source_type,
        program=None,
    )

    class DB:
        def get(self, model, found_id):
            assert found_id == document_id
            return document

    monkeypatch.setattr(
        "server.modules.evaluations.context.resolve_document_pdf_path",
        lambda path: path,
    )
    monkeypatch.setattr(
        "server.modules.evaluations.context.prepare_canonical_source",
        lambda path: "canonical full SLM body",
    )
    monkeypatch.setattr(
        EvaluationContextBuilder, "_load_active_prompt_versions", lambda self: {}
    )
    monkeypatch.setattr(
        EvaluationContextBuilder, "_build_precomputed_context", lambda *a, **k: {}
    )
    agent = (
        get_agent_class("coordinator")()
        if agent_name == "coordinator"
        else get_agent_class(agent_name)()
    )
    return document_id, EvaluationContextBuilder(DB(), [agent])


def _build(builder, document_id, snapshots):
    return builder.build(
        chunks=[SimpleNamespace(chunk_id=uuid4(), page_number=1, text="chunk")],
        query_text=None,
        context={"document_id": document_id},
        form_snapshots=snapshots,
    )


def test_context_builder_prepares_and_freezes_retrieval_for_builtin_v4(monkeypatch):
    document_id, builder = _builder(monkeypatch)
    captured = {}
    monkeypatch.setattr(
        "equiped_harness.agents.coordinator.evidence.retrieval_queries",
        lambda snapshot: {"organization": "org", "assessment": "assess"},
    )

    def build_index(**kwargs):
        captured.update(kwargs)
        return {
            "contract": "slm_retrieval.v2",
            "document_id": str(document_id),
            "source_hash": "hash",
            "embedding_model": "local-model",
            "rankings": {"OP-01": ["slm-0001"]},
            "passages": {"slm-0001": {"start": 0, "end": 12}},
        }

    monkeypatch.setattr(
        "server.modules.embeddings.slm_retrieval.build_slm_retrieval", build_index
    )
    prepared = _build(builder, document_id, (_coord_snapshot(),))

    assert captured["document_id"] == document_id
    assert captured["canonical_source_text"] == "canonical full SLM body"
    assert "granular" not in captured
    assert set(captured["queries"]) == {"organization", "assessment"}
    assert prepared.canonical_source_text == "canonical full SLM body"
    assert prepared.source_retrieval["rankings"]["OP-01"] == ("slm-0001",)
    assert prepared.source_retrieval["passages"]["slm-0001"]["end"] == 12
    with pytest.raises(TypeError):
        prepared.source_retrieval["rankings"]["OP-01"] = ("altered",)


@pytest.mark.parametrize(
    ("agent_name", "snapshot_agent", "version"),
    [
        ("sme", "sme", 4),
        ("coordinator", "coordinator", 3),
        ("coordinator", "coordinator", 2),
    ],
)
def test_context_builder_skips_non_coordinator_and_legacy_adapter(
    monkeypatch, agent_name, snapshot_agent, version
):
    document_id, builder = _builder(monkeypatch, agent_name=agent_name)
    monkeypatch.setattr(
        "server.modules.embeddings.slm_retrieval.build_slm_retrieval",
        lambda **kwargs: pytest.fail("retrieval indexing must be skipped"),
    )
    snapshot = (
        _coord_snapshot(version)
        if snapshot_agent == "coordinator"
        else _make_dummy_snapshot(snapshot_agent)
    )

    prepared = _build(builder, document_id, (snapshot,))
    assert prepared.source_retrieval is None


def test_context_builder_rejects_non_slm_and_sanitizes_index_failure(monkeypatch):
    document_id, builder = _builder(monkeypatch, source_type="reference")
    with pytest.raises(
        SupervisorExecutionError,
        match="SLM evidence retrieval preparation failed",
    ):
        _build(builder, document_id, (_coord_snapshot(),))

    document_id, builder = _builder(monkeypatch)
    monkeypatch.setattr(
        "server.modules.embeddings.slm_retrieval.build_slm_retrieval",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("secret query/body")),
    )
    with pytest.raises(
        SupervisorExecutionError,
        match="SLM evidence retrieval preparation failed",
    ) as err:
        _build(builder, document_id, (_coord_snapshot(),))
    assert "secret query/body" not in str(err.value)


def test_context_builder_rejects_retrieval_bound_to_another_document(monkeypatch):
    document_id, builder = _builder(monkeypatch)
    monkeypatch.setattr(
        "server.modules.embeddings.slm_retrieval.build_slm_retrieval",
        lambda **kwargs: {
            "contract": "slm_retrieval.v2",
            "document_id": str(uuid4()),
            "source_hash": "hash",
            "embedding_model": "local-model",
            "rankings": {},
        },
    )
    with pytest.raises(
        SupervisorExecutionError,
        match="SLM evidence retrieval preparation failed",
    ):
        _build(builder, document_id, (_coord_snapshot(),))


@pytest.mark.parametrize(
    "builtin,version", [(True, 3), (True, 4), (False, 4), (True, 2)]
)
def test_dispatch_routes_retrieval_only_to_builtin_coordinator_v4(
    monkeypatch, builtin, version
):
    evaluation_id = uuid4()
    document_id = uuid4()
    snapshot = _coord_snapshot(version, evaluation_id)
    retrieval = {"contract": "slm_retrieval.v2", "rankings": {"OP-01": ["p1"]}}
    seen = {}

    class CustomCoordinator:
        agent_name = "coordinator"

        def run(self, **kwargs):
            seen["custom"] = kwargs
            return _result(evaluation_id, document_id)

    agent = get_agent_class("coordinator")() if builtin else CustomCoordinator()
    from server.modules.evaluations import dispatch

    monkeypatch.setattr(dispatch, "get_llm_client_for_agent", lambda name: object())
    monkeypatch.setattr(dispatch, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(dispatch, "HarnessModelClient", lambda client: client)
    monkeypatch.setattr(dispatch, "execution_config_from_settings", lambda s: object())
    monkeypatch.setattr(dispatch, "tool_config_from_settings", lambda s: object())

    def evaluate(request, *args, **kwargs):
        seen["request"] = request
        return _result(evaluation_id, document_id)

    monkeypatch.setattr(dispatch, "evaluate", evaluate)
    AgentDispatcher([agent])._run_single_agent(
        agent=agent,
        agent_name="coordinator",
        evaluation_id=evaluation_id,
        document_id=document_id,
        form_snapshot=snapshot,
        chunk_infos=(),
        context_text="text",
        prompt_row=None,
        reference_document_ids={},
        precomputed_context={},
        provenance={},
        policy_evidence={},
        roadmap_context=None,
        source_retrieval=retrieval,
    )
    if builtin:
        assert isinstance(seen["request"], EvaluationRequest)
        if version == 4:
            routed = seen["request"].source_retrieval
            assert routed["contract"] == retrieval["contract"]
            assert routed["rankings"]["OP-01"] == ("p1",)
        else:
            assert seen["request"].source_retrieval is None
    else:
        assert "source_retrieval" not in seen["custom"]


def _result(evaluation_id, document_id):
    return AgentEvaluationResult(
        agent_name="coordinator",
        evaluation_id=evaluation_id,
        document_id=document_id,
        subtotal=1,
        criterion_scores=(),
        summary="ok",
        model_name="test",
        processing_seconds=0,
        token_count=0,
        prompt_version_id=None,
        success=True,
    )
