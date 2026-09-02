"""Tests for Coordinator Rubric v3 seed helper (10 independent criteria)."""

from __future__ import annotations

from server.modules.rubrics.models import (
    RubricAgentActivation,
    RubricCriterion,
    RubricDomain,
    RubricSet,
)
from server.scripts.seed_rubrics import seed_coordinator_v3_if_needed

CODES = {
    "OP-01",
    "OP-02",
    "OP-03",
    "OP-04",
    "OP-05",
    "A-01",
    "A-02",
    "A-03",
    "A-04",
    "A-05",
}


def test_seed_coordinator_v3_creates_and_activates_ten_criteria(db_session):
    result = seed_coordinator_v3_if_needed(db_session)
    db_session.flush()
    assert result is not None
    assert result.version_number == 3
    assert result.adapter_version == 2
    assert result.status == "published"

    crits = (
        db_session.query(RubricCriterion)
        .join(RubricDomain)
        .filter(RubricDomain.rubric_set_id == result.rubric_set_id)
        .all()
    )
    assert {c.criterion_code for c in crits} == CODES
    a05 = next(c for c in crits if c.criterion_code == "A-05")
    assert a05.scoring_strategy == "curriculum_alignment"

    activation = (
        db_session.query(RubricAgentActivation)
        .filter_by(agent_id="coordinator")
        .one()
    )
    assert activation.rubric_set_id == result.rubric_set_id


def test_seed_coordinator_v3_is_idempotent(db_session):
    first = seed_coordinator_v3_if_needed(db_session)
    db_session.flush()
    second = seed_coordinator_v3_if_needed(db_session)
    db_session.flush()
    assert second is not None
    assert second.rubric_set_id == first.rubric_set_id
    count = (
        db_session.query(RubricSet)
        .filter_by(agent_id="coordinator", version_number=3)
        .count()
    )
    assert count == 1
