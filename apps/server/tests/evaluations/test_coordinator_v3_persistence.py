"""Versioned Coordinator advisory survives storage, replay and result presentation."""

import json
import runpy
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest
from equiped_harness.contracts.snapshots import (
    build_evaluation_form_snapshot,
    verify_evaluation_form_snapshot,
)
from server.modules.rubrics.models import EvaluationFormSnapshot
from server.modules.synthesis.exceptions import EvaluationResultIntegrityError
from server.modules.synthesis.matrix import (
    compute_synthesized_score,
    upsert_monitoring_matrix,
)
from server.modules.synthesis.models import (
    AgentResult,
    CriterionScore,
    EvaluationFlag,
)
from server.modules.synthesis.result_integrity import (
    build_persistable_agent_result,
    coordinator_current_contract,
)
from server.modules.synthesis.service import (
    get_evaluation_results,
    get_master_synthesis_detail,
    load_verified_persisted_agent_results,
)
from server.tests.evaluations.test_persistence_integrity import _setup_evaluation


def test_unmarked_historical_coordinator_bundle_resolves_as_v1():
    assert (
        coordinator_current_contract(
            {"criteria": {}, "objective": {}, "curriculum": {}, "catalog": []}
        )
        == "coordinator_current.v1"
    )


def _as_historical_v1(result):
    """Project a frozen v3 fixture into the unmarked v1 storage shape."""
    bundle = result.metadata["current_bundle"]
    catalog = bundle["catalog"]
    first_slm = next(item for item in catalog if item["source"] == "slm")
    criterion_facts = {}
    scores = []
    for score in result.criterion_scores:
        if score.criterion_id == "A-05":
            continue
        criterion_facts[score.criterion_id] = {
            "kind": "guidance",
            "status": "supported",
            "score": score.score,
            "evidence_id": first_slm["source_id"],
        }
        scores.append(
            replace(
                score,
                justification=(
                    f"{score.criterion_title}: supported evidence; "
                    f"deterministic score {score.score}/4."
                ),
                evidence=(first_slm["text"],),
            )
        )
    objective_rows = [
        {"objective_id": row["objective_id"], "source_ids": row["source_ids"]}
        for row in bundle["objective"]["rows"]
    ]
    curriculum_rows = [
        {"objective_id": row["objective_id"], "source_ids": row["source_ids"]}
        for row in bundle["curriculum"]["rows"]
    ]
    source_by_id = {item["source_id"]: item["text"] for item in catalog}
    matched = sum(bool(row["source_ids"]) for row in objective_rows)
    score = (
        4
        if matched / len(objective_rows) >= 0.8
        else 3
        if matched / len(objective_rows) >= 0.5
        else 2
        if matched / len(objective_rows) >= 0.2
        else 1
    )
    a05 = next(row for row in result.criterion_scores if row.criterion_id == "A-05")
    a05 = replace(
        a05,
        score=score,
        justification=(
            f"Objective gauging: {matched}/{len(objective_rows)} objectives supported "
            f"({matched / len(objective_rows) * 100:.1f}%); "
            f"deterministic score {score}."
        ),
    )
    scores.append(a05)
    c_matched = sum(bool(row["source_ids"]) for row in curriculum_rows)
    c_score = (
        4
        if c_matched / len(curriculum_rows) >= 0.8
        else 3
        if c_matched / len(curriculum_rows) >= 0.5
        else 2
        if c_matched / len(curriculum_rows) >= 0.2
        else 1
    )
    advisory = result.advisory_outputs.model_copy(
        update={
            "score": c_score,
            "justification": (
                f"Curriculum alignment: {c_matched}/{len(curriculum_rows)} objectives "
                f"supported; deterministic score {c_score}."
            ),
            "objective_matches": tuple(
                match.model_copy(
                    update={
                        "matched": bool(row["source_ids"]),
                        "excerpt": source_by_id[row["source_ids"][0]]
                        if row["source_ids"]
                        else "",
                    }
                )
                for match, row in zip(
                    result.advisory_outputs.objective_matches,
                    curriculum_rows,
                    strict=True,
                )
            ),
        }
    )
    legacy_bundle = {
        "criteria": criterion_facts,
        "objective": {
            "assessment_available": bundle["objective"]["assessment_available"],
            "rows": objective_rows,
        },
        "curriculum": {"rows": curriculum_rows},
        "catalog": catalog,
    }
    metadata = dict(result.metadata)
    group_responses = dict(metadata["group_responses"])
    group_responses["__current_bundle__"] = legacy_bundle
    metadata.update(
        execution_contract="coordinator_current.v1",
        current_bundle=legacy_bundle,
        group_responses=group_responses,
    )
    return replace(
        result,
        criterion_scores=tuple(scores),
        subtotal=sum(row.score for row in scores) / len(scores),
        advisory_outputs=advisory,
        metadata=metadata,
    )


def _insert_historical_result(db_session, result, snapshot, *, chunk_id=None):
    """Insert a validated saved result without treating it as a new run."""
    persistable = build_persistable_agent_result(result, snapshot, persisted_read=True)
    result_id = uuid4()
    result_row = AgentResult(
        agent_result_id=result_id,
        evaluation_id=persistable.evaluation_id,
        document_id=persistable.document_id,
        agent_name=persistable.agent_name,
        prompt_version_id=persistable.prompt_version_id,
        subtotal=persistable.subtotal,
        processing_seconds=persistable.processing_seconds,
        token_count=persistable.token_count,
        model_name=persistable.model_name,
        summary=persistable.summary,
        success=persistable.success,
        error_message=persistable.error_message,
        raw_response=persistable.raw_response,
        prompt_text=persistable.prompt_text,
        group_prompts=(
            json.loads(persistable.group_prompts_json)
            if persistable.group_prompts_json
            else None
        ),
        group_responses=(
            json.loads(persistable.group_responses_json)
            if persistable.group_responses_json
            else None
        ),
        envelope_status=(
            json.loads(persistable.envelope_status_json)
            if persistable.envelope_status_json
            else None
        ),
        provenance=(
            json.loads(persistable.provenance_json)
            if persistable.provenance_json
            else None
        ),
        advisory_outputs=(
            json.loads(persistable.advisory_outputs_json)
            if persistable.advisory_outputs_json
            else None
        ),
        form_snapshot_id=persistable.form_snapshot_id,
    )
    db_session.add(result_row)
    db_session.flush()
    for score in persistable.criterion_scores:
        db_session.add(
            CriterionScore(
                agent_result_id=result_id,
                evaluation_id=persistable.evaluation_id,
                document_id=persistable.document_id,
                criterion_id=score.criterion_id,
                criterion_title=score.criterion_title,
                score=score.score,
                justification=score.justification,
                evidence=score.evidence_json,
                chunk_ids=(json.dumps([str(chunk_id)]) if chunk_id else None),
            )
        )
    db_session.flush()
    return result_row


def persist_v3(db_session):
    owner, doc, job, chunk = _setup_evaluation(db_session)
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
    old = verify_evaluation_form_snapshot(
        row.snapshot_id,
        row.evaluation_id,
        row.agent_id,
        row.rubric_set_id,
        row.adapter_key,
        row.adapter_version,
        row.snapshot_hash,
        row.snapshot_payload,
    )
    fixture_path = (
        Path(__file__).resolve().parents[4]
        / "libs/evaluation-harness/tests/agents/coordinator/historical_fixture.py"
    )
    historical_snapshot, historical_result = runpy.run_path(str(fixture_path))[
        "load_historical_fixture"
    ](3)
    form = historical_snapshot.form.model_copy(
        update={"rubric_set_id": old.rubric_set_id}
    )
    snapshot = build_evaluation_form_snapshot(job.evaluation_id, form, row.snapshot_id)
    row.adapter_version = 3
    row.snapshot_hash = snapshot.snapshot_hash
    row.snapshot_payload = snapshot.snapshot_payload.model_dump(mode="json")
    db_session.flush()
    metadata = dict(historical_result.metadata)
    bundle = dict(metadata["current_bundle"])
    retrieval = dict(bundle["source_retrieval"])
    retrieval["document_id"] = str(doc.document_id)
    bundle["source_retrieval"] = retrieval
    metadata["current_bundle"] = bundle
    group_responses = dict(metadata["group_responses"])
    group_responses["__current_bundle__"] = bundle
    metadata["group_responses"] = group_responses
    normalized_scores = tuple(
        replace(
            score,
            evidence=tuple(score.evidence),
            chunk_ids=tuple(score.chunk_ids),
        )
        for score in historical_result.criterion_scores
    )
    coordinator = replace(
        historical_result,
        evaluation_id=job.evaluation_id,
        document_id=doc.document_id,
        metadata=metadata,
        criterion_scores=normalized_scores,
    )
    _insert_historical_result(
        db_session, coordinator, snapshot, chunk_id=chunk.chunk_id
    )
    return owner, doc, job, coordinator


def test_unmarked_historical_v1_bundle_survives_persisted_readback(db_session):
    owner, doc, job, chunk = _setup_evaluation(db_session)
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
    old = verify_evaluation_form_snapshot(
        row.snapshot_id,
        row.evaluation_id,
        row.agent_id,
        row.rubric_set_id,
        row.adapter_key,
        row.adapter_version,
        row.snapshot_hash,
        row.snapshot_payload,
    )
    fixture_path = (
        Path(__file__).resolve().parents[4]
        / "libs/evaluation-harness/tests/agents/coordinator/historical_fixture.py"
    )
    fixture_snapshot, fixture_result = runpy.run_path(str(fixture_path))[
        "load_historical_fixture"
    ](3)
    form = fixture_snapshot.form.model_copy(update={"rubric_set_id": old.rubric_set_id})
    snapshot = build_evaluation_form_snapshot(job.evaluation_id, form, row.snapshot_id)
    row.adapter_version = 3
    row.snapshot_hash = snapshot.snapshot_hash
    row.snapshot_payload = snapshot.snapshot_payload.model_dump(mode="json")
    db_session.flush()
    bundle = dict(fixture_result.metadata["current_bundle"])
    bundle["source_retrieval"]["document_id"] = str(doc.document_id)
    fixture_metadata = dict(fixture_result.metadata)
    fixture_metadata["current_bundle"] = bundle
    result = _as_historical_v1(
        replace(
            fixture_result,
            evaluation_id=job.evaluation_id,
            document_id=doc.document_id,
            metadata=fixture_metadata,
        )
    )
    _insert_historical_result(db_session, result, snapshot, chunk_id=chunk.chunk_id)
    stored = (
        db_session.query(AgentResult)
        .filter_by(evaluation_id=job.evaluation_id, agent_name="coordinator")
        .one()
    )
    assert "contract" not in stored.group_responses["__current_bundle__"]
    loaded = load_verified_persisted_agent_results(
        db_session, job.evaluation_id, doc.document_id
    )
    assert loaded[0].advisory_outputs == result.advisory_outputs.to_dict()
    response = get_evaluation_results(job.evaluation_id, owner.user_id, db_session)
    assert (
        response.domain_scores["coordinator"].advisory_outputs.score
        == result.advisory_outputs.score
    )


def test_advisory_roundtrip_is_not_an_official_row_or_flag(db_session):
    owner, doc, job, result = persist_v3(db_session)
    rows = load_verified_persisted_agent_results(
        db_session, job.evaluation_id, doc.document_id
    )
    coordinator = next(r for r in rows if r.agent_name == "coordinator")
    assert coordinator.advisory_outputs == result.advisory_outputs.to_dict()
    scores = (
        db_session.query(CriterionScore)
        .filter_by(agent_result_id=coordinator.agent_result_id)
        .all()
    )
    assert len(scores) == 10
    assert "C-01" not in {r.criterion_id for r in scores}
    assert (
        db_session.query(EvaluationFlag)
        .filter_by(evaluation_id=job.evaluation_id, criterion_id="C-01")
        .count()
        == 0
    )
    response = get_evaluation_results(job.evaluation_id, owner.user_id, db_session)
    assert response.domain_scores["coordinator"].advisory_outputs.score == 4
    assert response.domain_scores["coordinator"].subtotal == result.subtotal
    synthesis = compute_synthesized_score(rows)
    score_before = synthesis["synthesized_score"]
    coordinator.advisory_outputs = None
    assert compute_synthesized_score(rows)["synthesized_score"] == score_before
    db_session.rollback()


def test_advisory_reaches_admin_pillar_without_changing_composite(db_session):
    owner, doc, job, result = persist_v3(db_session)
    rows = load_verified_persisted_agent_results(
        db_session, job.evaluation_id, doc.document_id
    )
    synthesis = compute_synthesized_score(rows)
    upsert_monitoring_matrix(
        db_session,
        doc.document_id,
        job.evaluation_id,
        "COMPLETED",
        synthesized_score=synthesis["synthesized_score"],
        domain_scores=synthesis["domain_scores"],
    )
    db_session.commit()
    detail = get_master_synthesis_detail(db_session, doc.document_id)
    assert detail.pillars["coordinator"].advisory_outputs.score == 4
    assert detail.pillars["coordinator"].subtotal == result.subtotal


@pytest.mark.parametrize("mutation", ["missing", "score", "measurement"])
def test_tampered_persisted_supplement_fails_replay(db_session, mutation):
    owner, doc, job, _ = persist_v3(db_session)
    row = (
        db_session.query(AgentResult)
        .filter_by(evaluation_id=job.evaluation_id, agent_name="coordinator")
        .one()
    )
    if mutation == "missing":
        row.advisory_outputs = None
    elif mutation == "score":
        row.advisory_outputs = {**row.advisory_outputs, "score": 1}
    else:
        row.group_responses = {
            **row.group_responses,
            "envelope_2": {"objective_matches": []},
        }
    db_session.commit()
    with pytest.raises(EvaluationResultIntegrityError):
        load_verified_persisted_agent_results(
            db_session, job.evaluation_id, doc.document_id
        )
    with pytest.raises(EvaluationResultIntegrityError):
        get_evaluation_results(job.evaluation_id, owner.user_id, db_session)


@pytest.mark.parametrize("marker_tamper", ["missing", "unknown"])
def test_historical_current_bundle_tampering_is_rejected(db_session, marker_tamper):
    owner, doc, job, _result = persist_v3(db_session)
    stored = (
        db_session.query(AgentResult)
        .filter_by(evaluation_id=job.evaluation_id, agent_name="coordinator")
        .one()
    )
    original = json.loads(json.dumps(stored.group_responses))
    corrupted = json.loads(json.dumps(original))
    bundle = corrupted["__current_bundle__"]
    if marker_tamper == "missing":
        bundle.pop("contract")
    else:
        bundle["contract"] = "coordinator_current.v99"
    stored.group_responses = corrupted
    db_session.flush()
    with pytest.raises(EvaluationResultIntegrityError):
        load_verified_persisted_agent_results(
            db_session, job.evaluation_id, doc.document_id
        )
    with pytest.raises(EvaluationResultIntegrityError):
        get_evaluation_results(job.evaluation_id, owner.user_id, db_session)

    corrupted = json.loads(json.dumps(original))
    corrupted["__current_bundle__"]["criteria"] = {}
    stored.group_responses = corrupted
    db_session.flush()
    with pytest.raises(EvaluationResultIntegrityError):
        load_verified_persisted_agent_results(
            db_session, job.evaluation_id, doc.document_id
        )
    db_session.rollback()
