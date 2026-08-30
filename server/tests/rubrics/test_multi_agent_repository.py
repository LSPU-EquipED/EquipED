"""Tests for multi-agent locked active-form loader and snapshot persistence helper."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from server.modules.rubrics import (
    EvaluationFormSnapshot,
    FormDefinition,
    RubricAgentActivation,
    RubricSet,
    SnapshotIntegrityError,
    lock_and_load_requested_active_forms,
    persist_evaluation_form_snapshots,
)
from sqlalchemy import event

from .helpers import seed_all_rubrics


def _get_active_bindings(session) -> dict[str, uuid.UUID]:
    activations = session.query(RubricAgentActivation).all()
    return {act.agent_id: act.rubric_set_id for act in activations}


# ---------------------------------------------------------------------------
# lock_and_load_requested_active_forms Tests
# ---------------------------------------------------------------------------


def test_lock_and_load_requested_active_forms_success_all_agents(db_session):
    seed_all_rubrics(db_session)
    bindings = _get_active_bindings(db_session)
    assert set(bindings.keys()) >= {"sme", "coordinator", "gad", "itso"}

    forms = lock_and_load_requested_active_forms(db_session, bindings)

    assert set(forms.keys()) == set(bindings.keys())
    for agent_id, form in forms.items():
        assert isinstance(form, FormDefinition)
        assert form.agent_id == agent_id
        assert form.rubric_set_id == bindings[agent_id]
        assert len(form.domains) > 0


def test_lock_and_load_requested_active_forms_partial_subset(db_session):
    seed_all_rubrics(db_session)
    bindings = _get_active_bindings(db_session)
    partial_bindings = {"gad": bindings["gad"], "sme": bindings["sme"]}

    forms = lock_and_load_requested_active_forms(db_session, partial_bindings)

    assert list(forms.keys()) == ["gad", "sme"]
    assert forms["gad"].agent_id == "gad"
    assert forms["sme"].agent_id == "sme"


def test_lock_and_load_query_boundedness_and_locking_order(db_session):
    seed_all_rubrics(db_session)
    bindings = _get_active_bindings(db_session)

    statements = []

    def _capture_statements(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    conn = db_session.connection()
    event.listens_for(conn, "before_cursor_execute")(_capture_statements)
    try:
        forms = lock_and_load_requested_active_forms(db_session, bindings)
    finally:
        event.remove(conn, "before_cursor_execute", _capture_statements)

    assert len(forms) == len(bindings)
    # Exactly 4 bounded queries:
    # 1. RubricAgentActivation (locked in agent_id order)
    # 2. RubricSet (locked in rubric_set_id order)
    # 3. RubricDomain
    # 4. RubricCriterion
    assert len(statements) == 4

    # Verify query 1 accesses rubric_agent_activations with ORDER BY agent_id
    assert "rubric_agent_activations" in statements[0].lower()
    assert "order by rubric_agent_activations.agent_id" in statements[0].lower()

    # Verify query 2 accesses rubric_sets with ORDER BY rubric_set_id
    assert "rubric_sets" in statements[1].lower()
    assert "order by rubric_sets.rubric_set_id" in statements[1].lower()


def test_lock_and_load_stale_revision_rejection(db_session):
    seed_all_rubrics(db_session)
    bindings = _get_active_bindings(db_session)

    # Supply an arbitrary non-active rubric_set_id for SME
    stale_bindings = dict(bindings)
    stale_bindings["sme"] = uuid.uuid4()

    with pytest.raises(ValueError, match="is not the current active revision"):
        lock_and_load_requested_active_forms(db_session, stale_bindings)


def test_lock_and_load_retired_active_pointer_rejection(db_session):
    seed_all_rubrics(db_session)
    bindings = _get_active_bindings(db_session)

    # Set SME status to retired directly in DB
    sme_set = db_session.query(RubricSet).filter_by(rubric_set_id=bindings["sme"]).one()
    sme_set.status = "retired"
    db_session.flush()

    with pytest.raises(ValueError, match="has invalid status 'retired'"):
        lock_and_load_requested_active_forms(db_session, bindings)


def test_lock_and_load_agent_mismatch_rejection(db_session):
    seed_all_rubrics(db_session)
    bindings = _get_active_bindings(db_session)

    # Point coordinator activation to SME rubric set in the DB
    coord_act = (
        db_session.query(RubricAgentActivation).filter_by(agent_id="coordinator").one()
    )
    coord_act.rubric_set_id = bindings["sme"]
    db_session.flush()

    # Request coordinator with SME set id
    mismatched = dict(bindings)
    mismatched["coordinator"] = bindings["sme"]

    with pytest.raises(ValueError, match="Agent mismatch"):
        lock_and_load_requested_active_forms(db_session, mismatched)


def test_lock_and_load_missing_activation_rejection(db_session):
    seed_all_rubrics(db_session)
    bindings = _get_active_bindings(db_session)

    db_session.query(RubricAgentActivation).filter_by(agent_id="itso").delete()
    db_session.flush()

    with pytest.raises(LookupError, match="Missing active published rubric set"):
        lock_and_load_requested_active_forms(db_session, bindings)


def test_lock_and_load_budget_validation_rejection(db_session):
    seed_all_rubrics(db_session)
    bindings = _get_active_bindings(db_session)

    low_budget_settings = MagicMock()
    low_budget_settings.sme_total_prompt_budget_chars = 10
    low_budget_settings.coordinator_total_prompt_budget_chars = 10
    low_budget_settings.gad_total_prompt_budget_chars = 10
    low_budget_settings.itso_total_prompt_budget_chars = 10

    with patch(
        "server.modules.rubrics.repository.get_settings",
        return_value=low_budget_settings,
    ):
        with pytest.raises(ValueError, match="failed capability manifest validation"):
            lock_and_load_requested_active_forms(db_session, bindings)


def test_lock_and_load_input_validation(db_session):
    seed_all_rubrics(db_session)
    bindings = _get_active_bindings(db_session)

    with pytest.raises(ValueError, match="must be a mapping"):
        lock_and_load_requested_active_forms(db_session, [("sme", bindings["sme"])])  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="cannot be empty"):
        lock_and_load_requested_active_forms(db_session, {})

    with pytest.raises(ValueError, match="invalid empty agent ID"):
        lock_and_load_requested_active_forms(db_session, {"": bindings["sme"]})

    with pytest.raises(ValueError, match="Unknown agent ID"):
        lock_and_load_requested_active_forms(
            db_session, {"unknown_agent": bindings["sme"]}
        )

    with pytest.raises(ValueError, match="exceeding maximum code length"):
        lock_and_load_requested_active_forms(db_session, {"a" * 100: bindings["sme"]})

    with pytest.raises(ValueError, match="must be a valid UUID"):
        lock_and_load_requested_active_forms(
            db_session,
            {"sme": "not-a-uuid"},  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# persist_evaluation_form_snapshots Tests
# ---------------------------------------------------------------------------


def test_persist_evaluation_form_snapshots_success(db_session):
    seed_all_rubrics(db_session)
    bindings = _get_active_bindings(db_session)
    forms = lock_and_load_requested_active_forms(db_session, bindings)

    eval_id = uuid.uuid4()
    dtos = persist_evaluation_form_snapshots(db_session, eval_id, forms)

    assert isinstance(dtos, tuple)
    assert len(dtos) == len(bindings)
    assert {d.agent_id for d in dtos} == set(bindings.keys())

    rows = (
        db_session.query(EvaluationFormSnapshot).filter_by(evaluation_id=eval_id).all()
    )
    assert len(rows) == len(bindings)


def test_persist_evaluation_form_snapshots_idempotent_identical_readback(db_session):
    seed_all_rubrics(db_session)
    bindings = _get_active_bindings(db_session)
    forms = lock_and_load_requested_active_forms(db_session, bindings)

    eval_id = uuid.uuid4()
    dtos_first = persist_evaluation_form_snapshots(db_session, eval_id, forms)
    db_session.flush()

    # Second call with identical forms returns identical readback DTOs
    dtos_second = persist_evaluation_form_snapshots(db_session, eval_id, forms)
    assert dtos_first == dtos_second

    # Database still has exactly len(bindings) rows
    rows = (
        db_session.query(EvaluationFormSnapshot).filter_by(evaluation_id=eval_id).all()
    )
    assert len(rows) == len(bindings)


def test_persist_evaluation_form_snapshots_mismatched_conflict_fails(db_session):
    seed_all_rubrics(db_session)
    bindings = _get_active_bindings(db_session)
    forms = lock_and_load_requested_active_forms(db_session, bindings)

    eval_id = uuid.uuid4()
    # First persist SME form
    persist_evaluation_form_snapshots(db_session, eval_id, [forms["sme"]])
    db_session.flush()

    # Force a different row in DB with agent_id="sme" (hash mismatch on conflict)
    db_session.query(EvaluationFormSnapshot).filter_by(
        evaluation_id=eval_id, agent_id="sme"
    ).update({"snapshot_hash": "a" * 64})
    db_session.flush()

    with pytest.raises(SnapshotIntegrityError):
        persist_evaluation_form_snapshots(db_session, eval_id, [forms["sme"]])


def test_persist_evaluation_form_snapshots_input_validation(db_session):
    seed_all_rubrics(db_session)
    bindings = _get_active_bindings(db_session)
    forms = lock_and_load_requested_active_forms(db_session, bindings)

    eval_id = uuid.uuid4()

    with pytest.raises(SnapshotIntegrityError, match="must be a valid UUID"):
        persist_evaluation_form_snapshots(db_session, "not-uuid", forms)  # type: ignore[arg-type]

    with pytest.raises(SnapshotIntegrityError, match="must not be None"):
        persist_evaluation_form_snapshots(db_session, eval_id, None)  # type: ignore[arg-type]

    with pytest.raises(SnapshotIntegrityError, match="cannot be empty"):
        persist_evaluation_form_snapshots(db_session, eval_id, [])

    with pytest.raises(
        SnapshotIntegrityError, match="All items in forms must be FormDefinition"
    ):
        persist_evaluation_form_snapshots(db_session, eval_id, ["not-a-form"])  # type: ignore[list-item]
