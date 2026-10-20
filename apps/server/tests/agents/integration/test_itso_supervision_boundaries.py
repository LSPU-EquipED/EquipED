"""Deterministic Oracle gates for ITSO supervision boundaries."""

from __future__ import annotations

import logging
import uuid
from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest
from equiped_harness.agents.itso.agent import ITSO
from equiped_harness.contracts.references import PolicyEvidenceSnapshot
from equiped_harness.contracts.results import AgentEvaluationResult
from equiped_harness.contracts.snapshots import build_evaluation_form_snapshot

from server.modules.evaluations import dispatch
from server.modules.evaluations.context import (
    PreparedEvaluationContext,
    PromptSnapshot,
)
from server.modules.evaluations.runner import Supervisor
from server.tests.agents.helpers import _make_dummy_snapshot


def _frozen_snapshot() -> PolicyEvidenceSnapshot:
    return PolicyEvidenceSnapshot(
        provenance=MappingProxyType(
            {"nested": MappingProxyType({"items": (MappingProxyType({"v": 1}),)})}
        ),
        policy_evidence=MappingProxyType(
            {"criteria": MappingProxyType({"ITSO-03": ("clause",)})}
        ),
    )


def _prompt(name: str) -> PromptSnapshot:
    return PromptSnapshot(version_id=f"prompt-{name}", prompt_text=f"{name} prompt")


def _result(name, evaluation_id, document_id, prompt_id):
    return AgentEvaluationResult(
        agent_name=name,
        evaluation_id=evaluation_id,
        document_id=document_id,
        subtotal=1.0,
        criterion_scores=(),
        summary="ok",
        model_name="result-model",
        processing_seconds=0.0,
        token_count=0,
        prompt_version_id=prompt_id,
    )


def _dispatch(
    monkeypatch,
    agents,
    *,
    provenance=None,
    policy=None,
    roadmap=None,
    temperature=0.17,
    adapter_version=1,
):
    evaluation_id, document_id = uuid.uuid4(), uuid.uuid4()
    clients = {
        name: type("Client", (), {"model": f"model-{name}"})()
        for name in {a.agent_name for a in agents}
    }
    settings = type(
        "Settings", (), {"get_agent_temperature": lambda self, _: temperature}
    )()
    monkeypatch.setattr(
        dispatch, "get_llm_client_for_agent", lambda name: clients[name]
    )
    monkeypatch.setattr(dispatch, "get_settings", lambda: settings)
    prompts = {a.agent_name: _prompt(a.agent_name) for a in agents}
    form_snapshots = tuple(
        _make_dummy_snapshot(a.agent_name, evaluation_id) for a in agents
    )
    if adapter_version != 1:
        form_snapshots = tuple(
            build_evaluation_form_snapshot(
                evaluation_id,
                snapshot.snapshot_payload.form.model_copy(
                    update={"adapter_version": adapter_version}
                ),
            )
            if snapshot.agent_id == "itso"
            else snapshot
            for snapshot in form_snapshots
        )
    result = dispatch.AgentDispatcher(agents).dispatch(
        evaluation_id=evaluation_id,
        document_id=document_id,
        chunk_infos=(MappingProxyType({"text": "slm"}),),
        form_snapshots=form_snapshots,
        context_text="query",
        prompt_versions=MappingProxyType(prompts),
        reference_document_ids=MappingProxyType({"ref": "id"}),
        precomputed_context=MappingProxyType({"rubric": ("r",)}),
        provenance=provenance,
        policy_evidence=policy,
        roadmap_context=roadmap,
        canonical_source_text="canonical source",
        authoritative_curriculum_text=None,
    )
    return result, clients, evaluation_id, document_id


@pytest.mark.parametrize(
    "returned_prompt_id, accepted", [(None, True), ("rogue", False)]
)
def test_builtin_itso_v3_omits_legacy_prompt_and_validates_null_identity(
    monkeypatch, returned_prompt_id, accepted
):
    from equiped_harness import EvaluationRequest

    captured = {}

    def evaluate(request, *_args, **_kwargs):
        captured["request"] = request
        return _result(
            "itso", request.evaluation_id, request.document_id, returned_prompt_id
        )

    monkeypatch.setattr(dispatch, "evaluate", evaluate)
    monkeypatch.setattr(dispatch, "execution_config_from_settings", lambda _: object())
    # Keep this dispatcher contract test independent of the separate five-item
    # adapter-3 manifest validation contract.
    monkeypatch.setattr(dispatch, "verify_evaluation_form_snapshot", lambda **_: None)
    (results, failures), _, _, _ = _dispatch(monkeypatch, [ITSO()], adapter_version=3)
    request = captured["request"]
    assert isinstance(request, EvaluationRequest)
    assert request.prompt_version is None
    assert request.prompt_version_id is None
    assert results[0].success is accepted
    assert ("itso" not in failures) is accepted
    if accepted:
        assert results[0].prompt_version_id is None
    else:
        assert failures["itso"].startswith("ValueError (reference:")


@pytest.mark.parametrize("adapter_version", [1, 2])
def test_retired_itso_adapters_reject_before_transport(adapter_version):
    from equiped_harness import EvaluationRequest, ExecutionConfig, evaluate

    evaluation_id, document_id = uuid.uuid4(), uuid.uuid4()
    snapshot = _make_dummy_snapshot("itso", evaluation_id)
    snapshot = build_evaluation_form_snapshot(
        evaluation_id,
        snapshot.snapshot_payload.form.model_copy(
            update={"adapter_version": adapter_version}
        ),
    )
    request = EvaluationRequest(
        evaluation_id=evaluation_id,
        document_id=document_id,
        form_snapshot=snapshot,
        chunk_infos=(),
    )

    class Client:
        calls = 0

        def generate_result(self, *args, **kwargs):
            self.calls += 1
            pytest.fail("retired ITSO adapters must be rejected before transport")

    client = Client()
    with pytest.raises(
        ValueError, match=f"Unsupported ITSO adapter version {adapter_version}"
    ):
        evaluate(request, client, ExecutionConfig())
    assert client.calls == 0


def test_itso_snapshot_recursively_freezes_nested_evidence():
    snapshot = _frozen_snapshot()
    with pytest.raises(TypeError):
        snapshot.provenance["nested"]["items"][0]["v"] = 2
    with pytest.raises(TypeError):
        snapshot.policy_evidence["criteria"]["ITSO-03"] += ("changed",)
    with pytest.raises(FrozenInstanceError):
        snapshot.provenance = None


@pytest.mark.parametrize("include_itso", [True, False])
def test_supervisor_skips_evidence_builder_for_legacy_rubric_runs(
    monkeypatch, include_itso
):
    class Agent:
        def __init__(self, name):
            self.agent_name = name

        def run(self, **kwargs):
            return _result(
                self.agent_name,
                kwargs["evaluation_id"],
                kwargs["document_id"],
                kwargs["prompt_version_id"],
            )

    agents = [Agent("sme")] + ([Agent("itso")] if include_itso else [])
    prepared = PreparedEvaluationContext(
        chunk_infos=(),
        query_text="",
        prompt_versions=MappingProxyType(
            {a.agent_name: _prompt(a.agent_name) for a in agents}
        ),
        reference_document_ids=MappingProxyType({}),
        precomputed_context=MappingProxyType({}),
        canonical_source_text="canonical source",
        authoritative_curriculum_text=None,
    )
    monkeypatch.setattr(
        "server.modules.evaluations.runner.EvaluationContextBuilder.build",
        lambda *a, **k: prepared,
    )
    builder = type("Builder", (), {"build": lambda self, _: _frozen_snapshot()})()
    monkeypatch.setattr(
        "server.modules.evaluations.runner.PolicyContextLoader",
        lambda db: builder,
    )
    calls = {"count": 0}
    original = builder.build

    def counted(chunks):
        calls["count"] += 1
        return original(chunks)

    builder.build = counted
    eval_id = uuid.uuid4()
    form_snapshots = tuple(
        build_evaluation_form_snapshot(
            eval_id,
            snapshot.snapshot_payload.form.model_copy(update={"adapter_version": 1}),
        )
        if snapshot.agent_id == "itso"
        else snapshot
        for snapshot in (_make_dummy_snapshot(a.agent_name, eval_id) for a in agents)
    )
    Supervisor(agents=agents).run_evaluation(
        evaluation_id=eval_id,
        document_id=uuid.uuid4(),
        chunks=[],
        form_snapshots=form_snapshots,
    )
    assert calls["count"] == 0


def test_supervisor_uses_policy_only_snapshot_for_adapter3(monkeypatch):
    class Agent:
        agent_name = "itso"

    agent = Agent()
    prepared = PreparedEvaluationContext(
        chunk_infos=(),
        query_text="",
        prompt_versions=MappingProxyType({"itso": _prompt("itso")}),
        reference_document_ids=MappingProxyType({}),
        precomputed_context=MappingProxyType({}),
        canonical_source_text="canonical source",
        authoritative_curriculum_text=None,
    )
    monkeypatch.setattr(
        "server.modules.evaluations.runner.EvaluationContextBuilder.build",
        lambda *a, **k: prepared,
    )

    builder_calls = {}

    def legacy_build(self, chunks):
        builder_calls["legacy"] = builder_calls.get("legacy", 0) + 1
        return _frozen_snapshot()

    def policy_build(self, plan):
        builder_calls["policy"] = builder_calls.get("policy", 0) + 1
        return _frozen_snapshot()

    builder = type(
        "Builder",
        (),
        {"build": legacy_build, "build_policy_context": policy_build},
    )()
    monkeypatch.setattr(
        "server.modules.evaluations.runner.PolicyContextLoader",
        lambda db: builder,
    )

    captured = {}

    def capture_dispatch(self, **kwargs):
        captured.update(kwargs)
        evaluation_id = kwargs["evaluation_id"]
        document_id = kwargs["document_id"]
        return ([_result("itso", evaluation_id, document_id, None)], {})

    monkeypatch.setattr(
        "server.modules.evaluations.runner.AgentDispatcher.dispatch",
        capture_dispatch,
    )
    evaluation_id = uuid.uuid4()
    snapshot = _make_dummy_snapshot("itso", evaluation_id)
    snapshot = build_evaluation_form_snapshot(
        evaluation_id,
        snapshot.snapshot_payload.form.model_copy(update={"adapter_version": 3}),
    )

    Supervisor(agents=[agent]).run_evaluation(
        evaluation_id=evaluation_id,
        document_id=uuid.uuid4(),
        chunks=[],
        form_snapshots=(snapshot,),
    )

    assert builder_calls == {"policy": 1}
    assert captured["provenance"] is not None
    assert captured["policy_evidence"] is not None
    assert captured["policy_evidence"]["criteria"]["ITSO-03"] == ("clause",)
    with pytest.raises(TypeError):
        captured["policy_evidence"]["criteria"]["ITSO-03"] = ("changed",)
    with pytest.raises(TypeError):
        captured["provenance"]["nested"]["items"][0]["v"] = 2


def test_dispatch_passes_exact_role_specific_keys(monkeypatch):
    seen = {}

    class Agent:
        def __init__(self, name):
            self.agent_name = name

        def run(self, **kwargs):
            seen[self.agent_name] = kwargs
            return _result(
                self.agent_name,
                kwargs["evaluation_id"],
                kwargs["document_id"],
                kwargs["prompt_version_id"],
            )

    provenance = MappingProxyType({"phase": "one"})
    policy = MappingProxyType({"policy": "only"})
    roadmap = MappingProxyType({"roadmap": "only"})
    _dispatch(
        monkeypatch,
        [Agent("sme"), Agent("itso"), Agent("coordinator")],
        provenance=provenance,
        policy=policy,
        roadmap=roadmap,
    )
    assert set(seen["sme"]) >= {"evaluation_id", "llm_client"}
    assert not set(seen["sme"]) & {
        "llm_temperature",
        "provenance",
        "policy_evidence",
        "roadmap_context",
    }
    assert {
        k: seen["itso"][k] for k in ("llm_temperature", "provenance", "policy_evidence")
    } == {
        "llm_temperature": 0.17,
        "provenance": {"phase": "one"},
        "policy_evidence": {"policy": "only"},
    }
    assert seen["coordinator"]["curriculum_id"] is None
    assert seen["coordinator"]["curriculum_context"] is None
    assert seen["coordinator"]["roadmap_context"] == {"roadmap": "only"}


def test_negative_itso_temperature_is_forwarded_unchanged(monkeypatch):
    class Itso:
        agent_name = "itso"

        def run(self, **kwargs):
            assert kwargs["llm_temperature"] == -7.5
            return _result(
                "itso",
                kwargs["evaluation_id"],
                kwargs["document_id"],
                kwargs["prompt_version_id"],
            )

    _dispatch(monkeypatch, [Itso()], temperature=-7.5)


def test_itso_failure_retains_client_duration_and_provenance(monkeypatch):
    ticks = iter((10.0, 10.0, 10.25, 10.25))
    monkeypatch.setattr(dispatch.time, "perf_counter", lambda: next(ticks))

    class Itso:
        agent_name = "itso"

        def run(self, **kwargs):
            raise RuntimeError("secret raw model policy excerpt")

    snapshot = _frozen_snapshot()
    (results, clients, *_) = _dispatch(
        monkeypatch,
        [Itso()],
        provenance=snapshot.provenance,
        policy=snapshot.policy_evidence,
    )
    failed = results[0][0]
    assert failed.model_name == clients["itso"].model and failed.processing_seconds > 0
    assert failed.provenance == {"nested": {"items": [{"v": 1}]}}
    assert (
        "secret" not in failed.error_message and "raw model" not in failed.error_message
    )


def test_failure_error_and_warning_are_safe(monkeypatch, caplog):
    secret = "UNIQUE_SECRET_POLICY_EXCERPT_RAW_MODEL"

    class Itso:
        agent_name = "itso"

        def run(self, **kwargs):
            raise ValueError(secret)

    with caplog.at_level(logging.WARNING):
        results, *_ = _dispatch(monkeypatch, [Itso()])
    assert secret not in (results[0][0].error_message or "")
    assert secret not in caplog.text and "ValueError" in (
        results[0][0].error_message or ""
    )


def test_outer_future_failure_retains_itso_provenance(monkeypatch):
    snapshot = _frozen_snapshot()
    monkeypatch.setattr(
        dispatch.AgentDispatcher,
        "_run_single_agent",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("outer secret")),
    )
    results, *_ = _dispatch(
        monkeypatch,
        [type("Itso", (), {"agent_name": "itso"})()],
        provenance=snapshot.provenance,
    )
    assert results[0][0].provenance == {"nested": {"items": [{"v": 1}]}}
    assert "outer secret" not in (results[0][0].error_message or "")


@pytest.mark.parametrize("malformed", [None, {}, "wrong"])
def test_malformed_agent_result_isolated_from_succeeding_peer(monkeypatch, malformed):
    class Agent:
        def __init__(self, name, value):
            self.agent_name = name
            self.value = value

        def run(self, **kwargs):
            if self.value == "ok":
                return _result(
                    self.agent_name,
                    kwargs["evaluation_id"],
                    kwargs["document_id"],
                    kwargs["prompt_version_id"],
                )
            return self.value

    dispatch_result, *_ = _dispatch(
        monkeypatch, [Agent("itso", malformed), Agent("sme", "ok")]
    )
    results, failures = dispatch_result
    assert {item.agent_name for item in results} == {"itso", "sme"}
    assert failures["itso"].startswith("TypeError (reference:")
    assert any(item.agent_name == "sme" and item.success for item in results)


@pytest.mark.parametrize("field", ["agent_name", "evaluation_id", "document_id"])
def test_wrong_result_identity_isolated_from_succeeding_peer(monkeypatch, field):
    class Agent:
        agent_name = "itso"

        def run(self, **kwargs):
            values = {
                "agent_name": "other",
                "evaluation_id": uuid.uuid4(),
                "document_id": uuid.uuid4(),
            }
            return _result(
                values.get(field, "itso"),
                values.get(field, kwargs["evaluation_id"]),
                values.get(field, kwargs["document_id"]),
                kwargs["prompt_version_id"],
            )

    class Peer:
        agent_name = "sme"

        def run(self, **kwargs):
            return _result(
                "sme",
                kwargs["evaluation_id"],
                kwargs["document_id"],
                kwargs["prompt_version_id"],
            )

    dispatch_result, *_ = _dispatch(monkeypatch, [Agent(), Peer()])
    results, failures = dispatch_result
    assert failures["itso"].startswith("ValueError (reference:")
    assert any(item.agent_name == "sme" and item.success for item in results)


def test_explicit_failure_is_sanitized_and_structured_fields_retained(
    monkeypatch, caplog
):
    secret = "SECRET_POLICY_TEXT"

    class Itso:
        agent_name = "itso"

        def run(self, **kwargs):
            return AgentEvaluationResult(
                agent_name="itso",
                evaluation_id=kwargs["evaluation_id"],
                document_id=kwargs["document_id"],
                subtotal=2.5,
                criterion_scores=(),
                summary="SECRET_POLICY_TEXT",
                model_name="returned-model",
                processing_seconds=4.25,
                token_count=9,
                prompt_version_id=kwargs["prompt_version_id"],
                success=False,
                error_message=secret,
                raw_response=secret,
                provenance={"actual_model": "safe-model"},
                metadata={"secret": secret},
                advisory_outputs={"secret": secret},
            )

    with caplog.at_level(logging.WARNING):
        dispatch_result, *_ = _dispatch(monkeypatch, [Itso()])
    results, failures = dispatch_result
    result = results[0]
    assert result.error_message.startswith("AgentReportedFailure (reference:")
    assert secret not in result.error_message
    assert secret not in failures["itso"]
    assert secret not in caplog.text
    assert result.raw_response is None
    assert (result.model_name, result.processing_seconds, result.prompt_version_id) == (
        "returned-model",
        4.25,
        result.prompt_version_id,
    )
    assert result.provenance == {"actual_model": "safe-model"}
    assert result.advisory_outputs is None


def test_failed_result_drops_secret_provenance(monkeypatch):
    secret = "SECRET_POLICY_TEXT"

    class Itso:
        agent_name = "itso"

        def run(self, **kwargs):
            return AgentEvaluationResult(
                agent_name="itso",
                evaluation_id=kwargs["evaluation_id"],
                document_id=kwargs["document_id"],
                subtotal=1.0,
                criterion_scores=(),
                summary="summary",
                model_name="model",
                processing_seconds=1.0,
                token_count=1,
                prompt_version_id=kwargs["prompt_version_id"],
                success=False,
                error_message="error",
                provenance={"actual_model": secret},
            )

    dispatch_result, *_ = _dispatch(monkeypatch, [Itso()])
    result = dispatch_result[0][0]
    assert result.provenance is None
    assert secret not in str(result)
