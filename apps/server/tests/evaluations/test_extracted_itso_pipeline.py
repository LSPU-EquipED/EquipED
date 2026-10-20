"""Regression coverage for the extracted ITSO public execution pipeline."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from equiped_harness import (
    AgentEvaluationResult,
    CompletionResult,
    CriterionScore,
    ToolConfig,
)
from equiped_harness.registry import get_agent_class
from equiped_harness.tools.http import Response

from server.core.config import Settings
from server.modules.admin.models import PromptVersion
from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.documents.models import Document, DocumentChunk
from server.modules.evaluations.dispatch import AgentDispatcher
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.rubrics.snapshots import resolve_or_reuse_evaluation_snapshots
from server.modules.synthesis.evaluation_results import get_evaluation_results
from server.modules.synthesis.matrix import (
    compute_synthesized_score,
    get_monitoring_matrix,
    upsert_monitoring_matrix,
)
from server.modules.synthesis.models import AgentResult
from server.modules.synthesis.persistence import persist_agent_outputs
from server.tests.rubrics.helpers import seed_all_rubrics


class ScriptedTransport:
    def __init__(self):
        self.requests = []

    async def get(self, request, deadline):
        self.requests.append(request)
        if request.kind == "duckduckgo":
            return Response(
                200,
                {},
                b'<a class="result__a" href="https://reference.example/study">'
                b"Privacy Engineering Study</a>",
            )
        if request.kind == "document":
            return Response(
                200,
                {"content-type": "text/html"},
                b"<html><head><title>Privacy Engineering Study</title></head>"
                b"<body><p>Privacy engineering protects institutional learning data."
                b" Secure handling reduces exposure.</p></body></html>",
            )
        return Response(404, {}, b"")


class SchemaModel:
    model = "scripted-model"

    def __init__(self, chunk_id):
        self.calls = []
        self.chunk_id = str(chunk_id)

    def generate_result(self, prompt, **kwargs):
        self.calls.append(prompt)
        data = json.loads(prompt.user_context)
        payload = data["response_example"]
        citation = "https://reference.example/study"
        for row in payload["criterion_scores"]:
            row["score"] = 3
            row["justification"] = (
                "The SLM states: Protect institutional learning data. "
                f"Reference comparison: [source 1] {citation}."
            )
            row["evidence"] = ["Protect institutional learning data."]
            row["chunk_ids"] = [self.chunk_id]
        return CompletionResult(json.dumps(payload), self.model, attempts=1)


def test_extracted_itso_dispatches_search_evaluates_and_persists(
    db_session, monkeypatch
):
    owner = create_user(
        db_session,
        name="ITSO owner",
        email="itso-extracted@ls.example",
        password="test-password",
        role=UserRole.FACULTY,
    )
    evaluation_id, document_id = uuid4(), uuid4()
    chunk_id = uuid4()
    source_text = (
        "SLM Content:\nProtect institutional learning data.\n\n"
        "References:\nAuthor, A. (2021). Privacy Engineering Study."
    )
    db_session.add(
        Document(
            document_id=document_id,
            title="ITSO regression SLM",
            program="BSCS",
            source_type="slm",
            file_path="uploads/itso-regression.pdf",
            uploaded_by=owner.user_id,
            uploaded_at=datetime.now(UTC),
            page_count=1,
            has_ocr_pages=False,
            processing_status="PROCESSED",
        )
    )
    db_session.add(
        DocumentChunk(
            chunk_id=chunk_id,
            document_id=document_id,
            source_type="slm",
            agent_domain="itso",
            page_number=1,
            text=source_text,
            token_count=24,
            is_ocr=False,
            chroma_stored=False,
        )
    )
    db_session.add(
        EvaluationJob(
            evaluation_id=evaluation_id,
            document_id=document_id,
            status=EvaluationStatus.EVALUATING.value,
            submitted_by=owner.user_id,
            target_agent="itso",
            partial_without_curriculum=False,
            confirmed_program="BSCS",
        )
    )
    db_session.commit()
    seed_all_rubrics(db_session)
    (snapshot,) = resolve_or_reuse_evaluation_snapshots(
        db_session, evaluation_id, ("itso",)
    )

    model = SchemaModel(chunk_id)
    transport = ScriptedTransport()
    settings = Settings(itso_verification_enabled=True)
    monkeypatch.setattr(
        "server.modules.evaluations.dispatch.get_llm_client_for_agent",
        lambda agent_name: model,
    )
    monkeypatch.setattr(
        "server.modules.evaluations.dispatch.get_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        "server.modules.evaluations.dispatch.tool_config_from_settings",
        lambda settings: ToolConfig(enabled=True, transport=transport),
    )

    results, failures = AgentDispatcher([get_agent_class("itso")()]).dispatch(
        evaluation_id=evaluation_id,
        document_id=document_id,
        chunk_infos=(
            {
                "chunk_id": str(chunk_id),
                "text": "Protect institutional learning data.",
            },
        ),
        form_snapshots=(snapshot,),
        context_text=source_text,
        prompt_versions={},
        reference_document_ids={},
        precomputed_context={},
        provenance={},
        policy_evidence={},
        roadmap_context=None,
        canonical_source_text=source_text,
    )

    assert not failures
    assert len(results) == 1 and results[0].success
    assert len(model.calls) == 2
    assert [request.kind for request in transport.requests] == [
        "duckduckgo",
        "document",
    ]
    assert any(
        "Protect institutional learning data." in " ".join(score.evidence)
        for score in results[0].criterion_scores
    )
    assert all(
        not score.evidence or all(quote in source_text for quote in score.evidence)
        for score in results[0].criterion_scores
    )

    persist_agent_outputs(
        db_session,
        evaluation_id,
        document_id,
        results,
        verify_ownership=lambda session: None,
    )
    saved = get_evaluation_results(
        evaluation_id,
        owner.user_id,
        db_session,
        evaluator_permissions=("itso",),
    )
    persisted_results = (
        db_session.query(AgentResult).filter_by(evaluation_id=evaluation_id).all()
    )
    synthesized = compute_synthesized_score(persisted_results)
    upsert_monitoring_matrix(
        db_session,
        document_id,
        evaluation_id,
        "IN_PROGRESS",
        synthesized_score=synthesized["synthesized_score"],
        domain_scores=synthesized["domain_scores"],
        target_agent="itso",
    )
    db_session.flush()
    matrix = get_monitoring_matrix(
        program="BSCS", status=None, page=1, page_size=10, db=db_session
    )
    assert saved.active_agents == ["itso"]
    assert saved.failed_agents == []
    assert matrix.items[0].evaluation_status == "IN_PROGRESS"


def test_custom_sme_and_itso_keep_their_specialist_signatures(db_session, monkeypatch):
    evaluation_id, document_id = uuid4(), uuid4()
    seed_all_rubrics(db_session)
    snapshots = resolve_or_reuse_evaluation_snapshots(
        db_session, evaluation_id, ("sme", "itso")
    )
    prompts = {
        name: PromptVersion(
            version_id=uuid4(),
            agent_id=name,
            version_number=1,
            prompt_text="active prompt",
            is_active=True,
        )
        for name in ("sme", "itso")
    }
    db_session.add_all(prompts.values())
    db_session.commit()

    class Model:
        model = "custom-model"

    monkeypatch.setattr(
        "server.modules.evaluations.dispatch.get_llm_client_for_agent",
        lambda agent_name: Model(),
    )
    observed = {}

    class CustomSME:
        agent_name = "sme"

        def run(
            self,
            *,
            evaluation_id,
            document_id,
            form_snapshot,
            chunk_infos,
            context_text,
            prompt_version,
            prompt_version_id,
            reference_document_ids,
            precomputed_context,
            llm_client,
            canonical_source_text,
        ):
            observed["sme"] = canonical_source_text
            return _custom_result("sme", evaluation_id, document_id, prompt_version_id)

    class CustomITSO:
        agent_name = "itso"

        def run(
            self,
            *,
            evaluation_id,
            document_id,
            form_snapshot,
            chunk_infos,
            context_text,
            prompt_version,
            prompt_version_id,
            reference_document_ids,
            precomputed_context,
            llm_client,
            llm_temperature,
            provenance,
            policy_evidence,
        ):
            observed["itso"] = (llm_temperature, provenance, policy_evidence)
            return _custom_result("itso", evaluation_id, document_id, prompt_version_id)

    for name, agent in (("sme", CustomSME()), ("itso", CustomITSO())):
        snapshot = next(item for item in snapshots if item.agent_id == name)
        results, failures = AgentDispatcher([agent]).dispatch(
            evaluation_id=evaluation_id,
            document_id=document_id,
            chunk_infos=(),
            form_snapshots=(snapshot,),
            context_text="prepared source",
            prompt_versions={name: prompts[name]},
            reference_document_ids={},
            precomputed_context={},
            provenance={"origin": "test"},
            policy_evidence={"policy": "test"},
            roadmap_context=None,
            canonical_source_text="canonical source",
        )
        assert not failures and results[0].success

    assert observed["sme"] == "canonical source"
    assert observed["itso"] == (0.0, {"origin": "test"}, {"policy": "test"})


def _custom_result(agent_name, evaluation_id, document_id, prompt_version_id):
    score = CriterionScore(
        criterion_id=f"{agent_name.upper()}-01",
        criterion_title="Custom criterion",
        score=3,
        justification="Supported by the supplied evidence.",
        chunk_ids=(),
        evidence=(),
    )
    return AgentEvaluationResult(
        agent_name=agent_name,
        evaluation_id=evaluation_id,
        document_id=document_id,
        subtotal=3.0,
        criterion_scores=(score,),
        summary="Custom evaluation result.",
        model_name="custom-model",
        processing_seconds=0.01,
        token_count=1,
        prompt_version_id=prompt_version_id,
        success=True,
    )


def test_lease_loss_during_search_prevents_model_and_result_persistence(
    db_session, monkeypatch
):
    from threading import Event, get_ident

    from equiped_harness.exceptions import SupervisorExecutionError

    from server.modules.evaluations.exceptions import EvaluationExecutionOwnershipError

    evaluation_id, document_id = uuid4(), uuid4()
    seed_all_rubrics(db_session)
    snapshots = resolve_or_reuse_evaluation_snapshots(
        db_session, evaluation_id, ("itso",)
    )
    started, release = Event(), Event()
    model = SchemaModel(uuid4())
    transport = ScriptedTransport()
    original_get = transport.get

    async def paused_get(request, deadline):
        started.set()
        assert release.wait(timeout=2), "owner heartbeat must run during search"
        return await original_get(request, deadline)

    transport.get = paused_get
    monkeypatch.setattr(
        "server.modules.evaluations.dispatch.get_llm_client_for_agent", lambda _: model
    )
    monkeypatch.setattr(
        "server.modules.evaluations.dispatch.get_settings",
        lambda: Settings(itso_verification_enabled=True),
    )
    monkeypatch.setattr(
        "server.modules.evaluations.dispatch.tool_config_from_settings",
        lambda _: ToolConfig(enabled=True, transport=transport),
    )
    monkeypatch.setattr(AgentDispatcher, "HEARTBEAT_INTERVAL_SECONDS", 0.01)
    owner_thread = get_ident()

    def heartbeat():
        assert get_ident() == owner_thread
        if started.is_set():
            release.set()
            raise EvaluationExecutionOwnershipError("Lost evaluation ownership")

    import pytest

    with pytest.raises(SupervisorExecutionError, match="heartbeat failed"):
        AgentDispatcher([get_agent_class("itso")()]).dispatch(
            evaluation_id=evaluation_id,
            document_id=document_id,
            chunk_infos=(),
            form_snapshots=snapshots,
            context_text="References:\nAuthor, A. (2021). Privacy Engineering Study.",
            prompt_versions={},
            reference_document_ids={},
            precomputed_context={},
            provenance={},
            policy_evidence={},
            roadmap_context=None,
            heartbeat_callback=heartbeat,
        )
    assert started.is_set()
    assert model.calls == []
    assert [request.kind for request in transport.requests] == ["duckduckgo"]
    assert db_session.query(AgentResult).count() == 0
