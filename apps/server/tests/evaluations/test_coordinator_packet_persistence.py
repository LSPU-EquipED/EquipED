"""Coordinator retrieval packets retain their integrity through DB readback."""

from __future__ import annotations

import copy
import runpy
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from server.modules.rubrics.models import EvaluationFormSnapshot
from server.modules.synthesis.exceptions import EvaluationResultIntegrityError
from server.modules.synthesis.models import AgentResult, CriterionScore
from server.modules.synthesis.service import (
    get_evaluation_results,
    load_verified_persisted_agent_results,
)
from server.tests.evaluations.test_coordinator_v3_persistence import (
    _insert_historical_result,
)
from server.tests.evaluations.test_persistence_integrity import _setup_evaluation

_COORDINATOR_TESTS = (
    Path(__file__).resolve().parents[4]
    / "libs/evaluation-harness/tests/agents/coordinator"
)
sys.path.insert(0, str(_COORDINATOR_TESTS))
_PACKET_HELPERS = runpy.run_path(str(_COORDINATOR_TESTS / "test_batch_integrity.py"))
_v5_result = _PACKET_HELPERS["_v5_result"]


def _persisted_packet_run(db_session, *, corrupt_finding=None):
    """Persist a frozen synthetic v5 packet result for DB readback checks."""
    del corrupt_finding  # The frozen v5 packet result already includes fallback data.
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

    from equiped_harness.contracts.snapshots import (
        build_evaluation_form_snapshot,
        verify_evaluation_form_snapshot,
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
    historical_snapshot, result = _v5_result()
    form = historical_snapshot.form.model_copy(
        update={"rubric_set_id": old.rubric_set_id}
    )
    snapshot = build_evaluation_form_snapshot(job.evaluation_id, form, row.snapshot_id)
    row.adapter_version = 3
    row.snapshot_hash = snapshot.snapshot_hash
    row.snapshot_payload = snapshot.snapshot_payload.model_dump(mode="json")
    db_session.flush()
    metadata = copy.deepcopy(result.metadata)
    bundle = metadata["current_bundle"]
    bundle["source_retrieval"]["document_id"] = str(doc.document_id)
    metadata["group_responses"]["__current_bundle__"] = bundle
    result = replace(
        result,
        evaluation_id=job.evaluation_id,
        document_id=doc.document_id,
        metadata=metadata,
    )
    _insert_historical_result(db_session, result, snapshot, chunk_id=chunk.chunk_id)
    return owner, doc, job, result


def test_retrieval_packets_roundtrip_with_stable_json(db_session):
    owner, doc, job, result = _persisted_packet_run(db_session)
    assert result.metadata["envelope_status"]["findings-assessment"] == "ok"

    loaded = load_verified_persisted_agent_results(
        db_session, job.evaluation_id, doc.document_id
    )
    assert len(loaded) == 1
    coordinator = loaded[0]
    assert (
        db_session.query(CriterionScore)
        .filter_by(agent_result_id=coordinator.agent_result_id)
        .count()
        == 10
    )
    assert coordinator.advisory_outputs == result.advisory_outputs.to_dict()
    assert coordinator.group_responses == result.metadata["group_responses"]
    bundle = coordinator.group_responses["__current_bundle__"]
    packet_ids = set(bundle["source_retrieval"]["packets"])
    assert packet_ids == {
        key
        for key in coordinator.group_responses
        if key in bundle["source_retrieval"]["packets"]
    }
    assert coordinator.envelope_status["findings-assessment"] == "ok"
    stored = (
        db_session.query(AgentResult)
        .filter_by(evaluation_id=job.evaluation_id, agent_name="coordinator")
        .one()
    )
    assert list(stored.group_responses) == sorted(stored.group_responses)
    assert list(stored.group_responses["__current_bundle__"]) == sorted(
        stored.group_responses["__current_bundle__"]
    )

    response = get_evaluation_results(job.evaluation_id, owner.user_id, db_session)
    block = response.domain_scores["coordinator"]
    assert block.advisory_outputs.score == result.advisory_outputs.score
    assert len(block.criteria) == 10


@pytest.mark.parametrize("tamper", ["remove", "change_source"])
def test_tampered_persisted_packet_fails_verified_read_and_result_api(
    db_session, tamper
):
    owner, doc, job, result = _persisted_packet_run(db_session)
    stored = (
        db_session.query(AgentResult)
        .filter_by(evaluation_id=job.evaluation_id, agent_name="coordinator")
        .one()
    )
    responses = copy.deepcopy(stored.group_responses)
    packet_id = next(
        key
        for key, response in responses.items()
        if key.startswith("ordinary-")
        and any(result.get("items") for result in response.get("results", []))
    )
    if tamper == "remove":
        del responses[packet_id]
    else:
        responses[packet_id]["results"][0]["items"][0]["source_id"] = "slm-9999"
    stored.group_responses = responses
    db_session.flush()

    with pytest.raises(EvaluationResultIntegrityError):
        load_verified_persisted_agent_results(
            db_session, job.evaluation_id, doc.document_id
        )
    with pytest.raises(EvaluationResultIntegrityError):
        get_evaluation_results(job.evaluation_id, owner.user_id, db_session)
    db_session.rollback()
