"""Regression: historical Coordinator adapter-v1 forms validate/load/activate.

The central validator resolves the manifest from the form's own
``adapter_version``, so a published v1 Coordinator form (single A-05
curriculum-alignment criterion) keeps working even though the current
Coordinator manifest is v2 (10 criteria). These tests seed a v1-shaped
published revision directly and exercise the stored-form paths end to end.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from server.modules.rubrics.models import (
    RubricAgentActivation,
    RubricCriterion,
    RubricDomain,
    RubricSet,
)
from server.modules.rubrics.repository import (
    activate_revision,
    get_active_form_definition,
    get_form_definition_by_id,
    load_active_form_definitions,
    lock_and_load_requested_active_forms,
    validate_form_definition,
)
from server.modules.rubrics.snapshots import persist_evaluation_form_snapshots


def _seed_coordinator_v1(session, *, version_number: int = 2) -> RubricSet:
    """Seed a published adapter-v1 Coordinator revision (single A-05 criterion)."""
    now = datetime.now(UTC)
    rubric_set = RubricSet(
        rubric_set_id=uuid.uuid4(),
        agent_id="coordinator",
        name="Coordinator Rubric v2",
        version_number=version_number,
        status="published",
        adapter_key="coordinator",
        adapter_version=1,
        published_at=now,
        published_by=None,
        created_by=None,
        created_at=now,
    )
    session.add(rubric_set)
    session.flush()

    domain = RubricDomain(
        rubric_domain_id=uuid.uuid4(),
        rubric_set_id=rubric_set.rubric_set_id,
        code="A",
        title="Assessment",
        display_order=1,
    )
    session.add(domain)
    session.flush()

    session.add(
        RubricCriterion(
            rubric_criterion_id=uuid.uuid4(),
            rubric_domain_id=domain.rubric_domain_id,
            criterion_code="A-05",
            title="Curriculum Alignment",
            description=(
                "Evaluate alignment between student learning material and "
                "confirmed course curriculum/syllabus topics."
            ),
            scoring_rule=(
                "Grounded curriculum alignment scoring for course syllabus topics."
            ),
            scoring_strategy="curriculum_alignment",
            strategy_config={"strategy": "curriculum_alignment"},
            display_order=1,
        )
    )
    session.flush()
    return rubric_set


def _point_activation(session, rubric_set: RubricSet) -> None:
    session.add(
        RubricAgentActivation(
            agent_id="coordinator",
            rubric_set_id=rubric_set.rubric_set_id,
            updated_by=None,
            updated_at=datetime.now(UTC),
        )
    )
    session.flush()


def test_historical_coordinator_v1_validates_via_central_function(db_session):
    rubric_set = _seed_coordinator_v1(db_session)

    form = get_form_definition_by_id(db_session, rubric_set.rubric_set_id)
    assert form is not None
    assert form.adapter_version == 1

    # Central function resolves the v1 manifest from the form itself.
    assert validate_form_definition(form).is_valid


def test_historical_coordinator_v1_loads_through_active_paths(db_session):
    rubric_set = _seed_coordinator_v1(db_session)
    _point_activation(db_session, rubric_set)

    active = get_active_form_definition(db_session, "coordinator")
    assert active is not None
    assert active.adapter_version == 1
    assert active.rubric_set_id == rubric_set.rubric_set_id

    bulk = load_active_form_definitions(db_session, ["coordinator"])
    assert bulk["coordinator"].rubric_set_id == rubric_set.rubric_set_id

    locked = lock_and_load_requested_active_forms(
        db_session, {"coordinator": rubric_set.rubric_set_id}
    )
    assert locked["coordinator"].rubric_set_id == rubric_set.rubric_set_id


def test_historical_coordinator_v1_activates_and_snapshots(db_session):
    active_set = _seed_coordinator_v1(db_session, version_number=2)
    _point_activation(db_session, active_set)
    rollback_target = _seed_coordinator_v1(db_session, version_number=4)

    activation = activate_revision(
        db_session,
        "coordinator",
        rollback_target.rubric_set_id,
        is_system=True,
    )
    assert activation.rubric_set_id == rollback_target.rubric_set_id

    forms = lock_and_load_requested_active_forms(
        db_session, {"coordinator": rollback_target.rubric_set_id}
    )
    dtos = persist_evaluation_form_snapshots(db_session, uuid.uuid4(), forms)
    assert len(dtos) == 1
    assert dtos[0].agent_id == "coordinator"
    assert dtos[0].adapter_version == 1
