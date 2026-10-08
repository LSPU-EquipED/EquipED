"""Versioned Coordinator advisory survives storage, replay and result presentation."""

import pytest
from server.modules.rubrics.models import EvaluationFormSnapshot
from server.modules.rubrics.snapshot_contracts import verify_evaluation_form_snapshot
from server.modules.synthesis.exceptions import EvaluationResultIntegrityError
from server.modules.synthesis.matrix import (
    compute_synthesized_score,
    upsert_monitoring_matrix,
)
from server.modules.synthesis.models import AgentResult, CriterionScore, EvaluationFlag
from server.modules.synthesis.service import (
    get_evaluation_results,
    get_master_synthesis_detail,
    load_verified_persisted_agent_results,
    persist_agent_outputs,
)
from server.tests.agents.coordinator.test_coordinator_v3 import make_v3_snapshot, run_v3
from server.tests.evaluations.snapshot_test_helpers import make_scheduled_agent_results
from server.tests.evaluations.test_persistence_integrity import _setup_evaluation


def persist_v3(db_session):
    owner, doc, job, _ = _setup_evaluation(db_session)
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
    snapshot = make_v3_snapshot(job.evaluation_id, old.form)
    row.adapter_version = 3
    row.snapshot_hash = snapshot.snapshot_hash
    row.snapshot_payload = snapshot.snapshot_payload.model_dump(mode="json")
    db_session.flush()
    _, coordinator = run_v3(snapshot=snapshot, document_id=doc.document_id)
    outputs = make_scheduled_agent_results(job.evaluation_id, doc.document_id)
    outputs = [coordinator if r.agent_name == "coordinator" else r for r in outputs]
    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        doc.document_id,
        outputs,
        verify_ownership=lambda db: None,
    )
    return owner, doc, job, coordinator


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
    assert response.domain_scores["coordinator"].subtotal == 3.9
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
