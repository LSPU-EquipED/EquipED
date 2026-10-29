"""Adapter-4 Coordinator results persist their reasoning and native provenance."""

from __future__ import annotations

import hashlib
import json
import runpy
from dataclasses import replace
from pathlib import Path

import pytest
from equiped_harness import CompletionResult, ExecutionConfig, evaluate
from equiped_harness.contracts.snapshots import build_evaluation_form_snapshot
from equiped_harness.runtime.source_retrieval import source_hash
from server.modules.rubrics.models import EvaluationFormSnapshot
from server.modules.synthesis.exceptions import EvaluationResultIntegrityError
from server.modules.synthesis.models import AgentGeneration, AgentResult, CriterionScore
from server.modules.synthesis.service import (
    get_evaluation_results,
    load_verified_persisted_agent_results,
    persist_agent_outputs,
)
from server.tests.evaluations.test_persistence_integrity import _setup_evaluation

_RUBRIC_HELPERS = runpy.run_path(
    str(
        Path(__file__).resolve().parents[4]
        / "libs/evaluation-harness/tests/agents/coordinator/test_rubric_pipeline.py"
    )
)
_rubric_request = _RUBRIC_HELPERS["rubric_request"]
_RubricFake = _RUBRIC_HELPERS["RubricFake"]


class _DifferentAlignmentFake(_RubricFake):
    """Give the advisory a different score to prove it is outside the mean."""

    def generate_result(self, prompt, **kwargs):
        result = super().generate_result(prompt, **kwargs)
        context = _RUBRIC_HELPERS["_input"](prompt)
        if context["criteria"][0]["criterion_id"] == "C-01":
            payload = json.loads(result.content)
            payload["results"][0]["score"] = 1
            result = CompletionResult(json.dumps(payload), self.model)
        return result


def _persisted_v6_run(db_session):
    owner, document, job, chunk = _setup_evaluation(db_session)
    job.target_agent = "coordinator"
    db_session.query(EvaluationFormSnapshot).filter(
        EvaluationFormSnapshot.evaluation_id == job.evaluation_id,
        EvaluationFormSnapshot.agent_id != "coordinator",
    ).delete(synchronize_session=False)
    row = (
        db_session.query(EvaluationFormSnapshot)
        .filter_by(evaluation_id=job.evaluation_id, agent_id="coordinator")
        .one()
    )

    request = _rubric_request()
    snapshot = build_evaluation_form_snapshot(
        job.evaluation_id, request.form_snapshot.form, snapshot_id=row.snapshot_id
    )
    row.rubric_set_id = snapshot.rubric_set_id
    row.adapter_version = 4
    row.snapshot_hash = snapshot.snapshot_hash
    row.snapshot_payload = snapshot.snapshot_payload.model_dump(mode="json")
    source = request.canonical_source_text
    request = replace(
        request,
        evaluation_id=job.evaluation_id,
        document_id=document.document_id,
        form_snapshot=snapshot,
        chunk_infos=({"chunk_id": str(chunk.chunk_id), "text": chunk.text},),
        source_retrieval={
            **request.source_retrieval,
            "document_id": str(document.document_id),
            "source_hash": source_hash(source),
        },
    )
    result = evaluate(request, _DifferentAlignmentFake(), ExecutionConfig())
    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        document.document_id,
        [result],
        verify_ownership=lambda _db: None,
    )
    return owner, document, job, request, result


def test_v6_native_generations_and_advisory_survive_persisted_read(db_session):
    owner, document, job, request, result = _persisted_v6_run(db_session)
    loaded = load_verified_persisted_agent_results(
        db_session, job.evaluation_id, document.document_id
    )
    assert len(loaded) == 1
    coordinator = loaded[0]
    persisted_scores = (
        db_session.query(CriterionScore)
        .filter_by(agent_result_id=coordinator.agent_result_id)
        .all()
    )
    assert len(persisted_scores) == 10
    assert coordinator.subtotal == 3.0
    assert coordinator.summary == result.summary
    assert coordinator.advisory_outputs == result.advisory_outputs.to_dict()
    assert coordinator.advisory_outputs["score"] == 1
    assert coordinator.subtotal == sum(score.score for score in persisted_scores) / 10

    bundle = coordinator.group_responses["__current_bundle__"]
    assert bundle["contract"] == "coordinator_current.v6"
    for score in persisted_scores:
        group = "organization" if score.criterion_id.startswith("OP-") else "assessment"
        response = coordinator.group_responses[group]
        finding = next(
            item
            for item in response["results"]
            if item["criterion_id"] == score.criterion_id
        )
        packets = bundle["packets"][group]
        expected_evidence = tuple(
            next(
                packet["text"] for packet in packets if packet["source_id"] == source_id
            )
            for source_id in finding["evidence_ids"]
        )
        assert score.score == finding["score"]
        assert score.justification == finding["finding"]
        assert tuple(json.loads(score.evidence)) == expected_evidence

    generations = (
        db_session.query(AgentGeneration)
        .filter_by(agent_result_id=coordinator.agent_result_id)
        .all()
    )
    assert len(generations) == 3
    by_unit = {generation.unit_key: generation for generation in generations}
    assert set(by_unit) == {"organization", "assessment", "alignment"}
    for unit, captured in by_unit.items():
        assert captured.capture_origin == "native"
        assert captured.form_snapshot_id == request.form_snapshot.snapshot_id
        assert (
            captured.prompt_sha256
            == hashlib.sha256(captured.prompt_text.encode()).hexdigest()
        )
        assert (
            captured.response_sha256
            == hashlib.sha256(captured.response_text.encode()).hexdigest()
        )
        assert captured.prompt_text == next(
            generation.prompt_text
            for generation in result.generations
            if generation.unit_key == unit
        )

    response = get_evaluation_results(job.evaluation_id, owner.user_id, db_session)
    block = response.domain_scores["coordinator"]
    assert len(block.criteria) == 10
    assert block.subtotal == 3.0
    assert block.advisory_outputs.score == 1


@pytest.mark.parametrize("tamper", ["capture", "supplement"])
def test_v6_saved_read_fails_closed_on_tampered_capture_or_supplement(
    db_session, tamper
):
    owner, document, job, _, _ = _persisted_v6_run(db_session)
    result_row = (
        db_session.query(AgentResult)
        .filter_by(evaluation_id=job.evaluation_id, agent_name="coordinator")
        .one()
    )
    if tamper == "capture":
        generation = (
            db_session.query(AgentGeneration)
            .filter_by(agent_result_id=result_row.agent_result_id, unit_key="alignment")
            .one()
        )
        generation.response_text += " altered"
    else:
        group_responses = dict(result_row.group_responses)
        alignment = dict(group_responses["alignment"])
        alignment["results"] = [dict(item) for item in alignment["results"]]
        alignment["results"][0]["finding"] = "Altered alignment finding."
        group_responses["alignment"] = alignment
        result_row.group_responses = group_responses
    db_session.flush()

    with pytest.raises(EvaluationResultIntegrityError):
        load_verified_persisted_agent_results(
            db_session, job.evaluation_id, document.document_id
        )
    with pytest.raises(EvaluationResultIntegrityError):
        get_evaluation_results(job.evaluation_id, owner.user_id, db_session)
    db_session.rollback()
