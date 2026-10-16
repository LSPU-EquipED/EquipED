from __future__ import annotations

import uuid

import pytest
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.rubrics.models import (
    EvaluationFormSnapshot,
    EvaluationRubricProvenance,
    RubricAgentActivation,
    RubricCriterion,
    RubricDomain,
    RubricSet,
)
from server.modules.rubrics.reset import (
    FRESH_V1_DRAFT_CONFIRMATION,
    RESET_CONFIRMATION,
    reset_coordinator_rubric,
)


def _authoring_tree(session, *, agent_id: str, version: int) -> RubricSet:
    rubric_set = RubricSet(
        rubric_set_id=uuid.uuid4(),
        agent_id=agent_id,
        name=f"{agent_id} v{version}",
        version_number=version,
        status="published",
        adapter_key=agent_id,
        adapter_version=1,
    )
    domain = RubricDomain(
        rubric_domain_id=uuid.uuid4(),
        rubric_set_id=rubric_set.rubric_set_id,
        code="A",
        title="Assessment",
        display_order=1,
    )
    criterion = RubricCriterion(
        rubric_criterion_id=uuid.uuid4(),
        rubric_domain_id=domain.rubric_domain_id,
        criterion_code="A-01",
        title="Criterion",
        description="Description",
        display_order=1,
    )
    session.add_all([rubric_set, domain, criterion])
    return rubric_set


def _snapshot(session, *, rubric_set: RubricSet, agent_id: str) -> None:
    session.add(
        EvaluationRubricProvenance(
            rubric_set_id=rubric_set.rubric_set_id,
            agent_id=agent_id,
            version_number=rubric_set.version_number,
            name=rubric_set.name,
            adapter_key=rubric_set.adapter_key,
            adapter_version=rubric_set.adapter_version,
        )
    )
    session.add(
        EvaluationFormSnapshot(
            snapshot_id=uuid.uuid4(),
            evaluation_id=uuid.uuid4(),
            agent_id=agent_id,
            rubric_set_id=rubric_set.rubric_set_id,
            snapshot_payload={"historical": True},
            snapshot_hash="a" * 64,
            adapter_key=agent_id,
            adapter_version=1,
        )
    )


def test_reset_requires_exact_confirmation_without_mutation(db_session):
    coordinator = _authoring_tree(db_session, agent_id="coordinator", version=1)
    db_session.add(
        RubricAgentActivation(
            agent_id="coordinator", rubric_set_id=coordinator.rubric_set_id
        )
    )
    db_session.flush()

    with pytest.raises(ValueError, match="requires confirmation"):
        reset_coordinator_rubric(db_session, confirmation="yes")

    assert db_session.get(RubricSet, coordinator.rubric_set_id) is not None
    assert (
        db_session.query(RubricAgentActivation)
        .filter_by(agent_id="coordinator")
        .count()
        == 1
    )


def test_reset_is_coordinator_scoped_and_preserves_snapshots_and_provenance(
    db_session,
):
    coordinator = _authoring_tree(db_session, agent_id="coordinator", version=1)
    other = _authoring_tree(db_session, agent_id="sme", version=1)
    db_session.add_all(
        [
            RubricAgentActivation(
                agent_id="coordinator", rubric_set_id=coordinator.rubric_set_id
            ),
            RubricAgentActivation(agent_id="sme", rubric_set_id=other.rubric_set_id),
        ]
    )
    _snapshot(db_session, rubric_set=coordinator, agent_id="coordinator")
    _snapshot(db_session, rubric_set=other, agent_id="sme")
    db_session.flush()

    report = reset_coordinator_rubric(
        db_session,
        confirmation=RESET_CONFIRMATION,
    )

    assert report.coordinator_rubric_set_ids == (coordinator.rubric_set_id,)
    assert report.snapshot_count_before == 2
    assert report.provenance_count_before == 2
    assert db_session.query(RubricSet).filter_by(agent_id="coordinator").count() == 0
    assert (
        db_session.query(RubricDomain)
        .filter_by(rubric_set_id=coordinator.rubric_set_id)
        .count()
        == 0
    )
    assert db_session.query(RubricCriterion).count() == 1
    assert db_session.query(RubricSet).filter_by(agent_id="sme").count() == 1
    assert db_session.query(EvaluationFormSnapshot).count() == 2
    assert db_session.query(EvaluationRubricProvenance).count() == 2
    assert (
        db_session.query(RubricAgentActivation).filter_by(agent_id="sme").count() == 1
    )


def test_reset_stops_on_count_expectation_without_mutation(db_session):
    coordinator = _authoring_tree(db_session, agent_id="coordinator", version=1)
    db_session.flush()

    with pytest.raises(RuntimeError, match="expected 2 Coordinator rubric set"):
        reset_coordinator_rubric(
            db_session,
            confirmation=RESET_CONFIRMATION,
            expected_rubric_set_count=2,
        )

    assert db_session.get(RubricSet, coordinator.rubric_set_id) is not None


def test_reset_stops_when_coordinator_job_is_in_flight(db_session):
    coordinator = _authoring_tree(db_session, agent_id="coordinator", version=1)
    db_session.add(
        EvaluationJob(
            evaluation_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            target_agent="coordinator",
            status=EvaluationStatus.EVALUATING.value,
        )
    )
    db_session.flush()

    with pytest.raises(RuntimeError, match="in-flight"):
        reset_coordinator_rubric(
            db_session,
            confirmation=RESET_CONFIRMATION,
        )

    assert db_session.get(RubricSet, coordinator.rubric_set_id) is not None


def test_fresh_v1_draft_requires_separate_confirmation_and_is_not_activated(db_session):
    with pytest.raises(ValueError, match="separate confirmation"):
        reset_coordinator_rubric(
            db_session,
            confirmation=RESET_CONFIRMATION,
            create_fresh_v1_draft=True,
        )

    report = reset_coordinator_rubric(
        db_session,
        confirmation=RESET_CONFIRMATION,
        create_fresh_v1_draft=True,
        fresh_draft_confirmation=FRESH_V1_DRAFT_CONFIRMATION,
    )

    assert report.fresh_draft_id is not None
    draft = db_session.get(RubricSet, report.fresh_draft_id)
    assert draft is not None
    assert draft.agent_id == "coordinator"
    assert draft.version_number == 1
    assert draft.status == "draft"
    assert draft.adapter_version == 3
    assert db_session.query(RubricAgentActivation).count() == 0
