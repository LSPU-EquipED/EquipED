"""Tests for bulk active-form loading and evaluation form snapshot resolution/reuse."""

from __future__ import annotations

import copy
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.documents.models import Document
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.rubrics import (
    EvaluationFormSnapshot,
    RubricAgentActivation,
    RubricSet,
    SnapshotIntegrityError,
    build_evaluation_form_snapshot,
    load_active_form_definitions,
    load_verified_evaluation_snapshots,
    resolve_or_reuse_evaluation_snapshots,
)
from sqlalchemy import event

from .conftest import _seed_all_rubrics


def _create_evaluation_job(session) -> uuid.UUID:
    """Create a minimal EvaluationJob in the test database and return evaluation_id."""
    user = create_user(
        session,
        name="Test User",
        email=f"user-{uuid.uuid4().hex[:8]}@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    session.flush()

    doc_id = uuid.uuid4()
    session.add(
        Document(
            document_id=doc_id,
            title="Test Syllabus",
            source_type="syllabus",
            file_path="uploads/test.pdf",
            uploaded_by=user.user_id,
            uploaded_at=datetime.now(UTC),
            page_count=1,
            has_ocr_pages=False,
            processing_status="PROCESSED",
        )
    )
    eval_id = uuid.uuid4()
    session.add(
        EvaluationJob(
            evaluation_id=eval_id,
            document_id=doc_id,
            status="QUEUED",
        )
    )
    session.commit()
    return eval_id


# ---------------------------------------------------------------------------
# Bulk Active Form Loader Tests
# ---------------------------------------------------------------------------


def test_load_active_form_definitions_bounded_query_shape(db_session) -> None:
    _seed_all_rubrics(db_session)

    query_count = 0

    def _count_queries(conn, cursor, statement, parameters, context, executemany):
        nonlocal query_count
        query_count += 1

    conn = db_session.connection()
    event.listens_for(conn, "before_cursor_execute")(_count_queries)
    try:
        forms = load_active_form_definitions(
            db_session, ("sme", "coordinator", "gad", "itso")
        )
    finally:
        event.remove(conn, "before_cursor_execute", _count_queries)

    # Exactly 3 bounded queries: (activation+rubric_set, domains, criteria)
    assert query_count == 3
    assert set(forms.keys()) == {"sme", "coordinator", "gad", "itso"}
    assert forms["sme"].agent_id == "sme"
    assert forms["coordinator"].agent_id == "coordinator"
    assert forms["gad"].agent_id == "gad"
    assert forms["itso"].agent_id == "itso"


def test_load_active_form_definitions_input_validation(db_session) -> None:
    _seed_all_rubrics(db_session)

    with pytest.raises(ValueError, match="non-string sequence"):
        load_active_form_definitions(db_session, "sme")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="non-string sequence"):
        load_active_form_definitions(db_session, b"sme")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="cannot be empty"):
        load_active_form_definitions(db_session, ())

    with pytest.raises(ValueError, match="Duplicate agent ID"):
        load_active_form_definitions(db_session, ("sme", "sme"))

    with pytest.raises(ValueError, match="Unknown agent ID"):
        load_active_form_definitions(db_session, ("sme", "nonexistent_agent"))

    with pytest.raises(ValueError, match="invalid empty agent ID"):
        load_active_form_definitions(db_session, ("sme", "   "))

    long_agent = "a" * 100
    with pytest.raises(ValueError, match="maximum code length"):
        load_active_form_definitions(db_session, ("sme", long_agent))


def test_load_active_form_definitions_missing_activation_fails(db_session) -> None:
    _seed_all_rubrics(db_session)
    db_session.query(RubricAgentActivation).filter_by(agent_id="itso").delete()
    db_session.commit()

    with pytest.raises(LookupError, match="Missing active published rubric set"):
        load_active_form_definitions(db_session, ("sme", "itso"))


def test_load_active_form_definitions_pointer_mismatch_fails(db_session) -> None:
    _seed_all_rubrics(db_session)
    # Point coordinator activation to SME rubric set
    sme_act = db_session.query(RubricAgentActivation).filter_by(agent_id="sme").one()
    coord_act = (
        db_session.query(RubricAgentActivation).filter_by(agent_id="coordinator").one()
    )
    coord_act.rubric_set_id = sme_act.rubric_set_id
    db_session.commit()

    with pytest.raises(ValueError, match="pointer agent mismatch"):
        load_active_form_definitions(db_session, ("sme", "coordinator"))


def test_load_active_form_definitions_non_published_status_fails(db_session) -> None:
    _seed_all_rubrics(db_session)
    sme_act = db_session.query(RubricAgentActivation).filter_by(agent_id="sme").one()
    sme_set = (
        db_session.query(RubricSet).filter_by(rubric_set_id=sme_act.rubric_set_id).one()
    )
    sme_set.status = "retired"
    db_session.commit()

    with pytest.raises(ValueError, match="invalid status 'retired'"):
        load_active_form_definitions(db_session, ("sme",))


# ---------------------------------------------------------------------------
# Snapshot Resolution & Verification Service Tests
# ---------------------------------------------------------------------------


def test_fresh_full_snapshot_creation(db_session) -> None:
    _seed_all_rubrics(db_session)
    eval_id = _create_evaluation_job(db_session)

    agents = ("sme", "coordinator", "gad", "itso")
    dtos = resolve_or_reuse_evaluation_snapshots(db_session, eval_id, agents)

    assert isinstance(dtos, tuple)
    assert len(dtos) == 4
    assert tuple(d.agent_id for d in dtos) == agents

    # Verify rows in database
    rows = (
        db_session.query(EvaluationFormSnapshot).filter_by(evaluation_id=eval_id).all()
    )
    assert len(rows) == 4
    row_map = {r.agent_id: r for r in rows}
    for dto in dtos:
        row = row_map[dto.agent_id]
        assert row.snapshot_id == dto.snapshot_id
        assert row.rubric_set_id == dto.rubric_set_id
        assert row.snapshot_hash == dto.snapshot_hash
        assert row.adapter_key == dto.adapter_key
        assert row.adapter_version == dto.adapter_version


def test_fresh_partial_snapshot_creation_exact_order(db_session) -> None:
    _seed_all_rubrics(db_session)
    eval_id = _create_evaluation_job(db_session)

    agents = ("gad", "sme")
    dtos = resolve_or_reuse_evaluation_snapshots(db_session, eval_id, agents)

    assert len(dtos) == 2
    assert tuple(d.agent_id for d in dtos) == ("gad", "sme")

    rows = (
        db_session.query(EvaluationFormSnapshot).filter_by(evaluation_id=eval_id).all()
    )
    assert len(rows) == 2
    assert {r.agent_id for r in rows} == {"gad", "sme"}


def test_valid_reuse_after_active_pointer_changes(db_session) -> None:
    _seed_all_rubrics(db_session)
    eval_id = _create_evaluation_job(db_session)

    agents = ("sme", "coordinator")
    dtos_initial = resolve_or_reuse_evaluation_snapshots(db_session, eval_id, agents)
    db_session.commit()

    # Change active pointer for coordinator to v1 retired or delete activation
    coord_v1 = (
        db_session.query(RubricSet)
        .filter_by(agent_id="coordinator", version_number=1)
        .one()
    )
    coord_act = (
        db_session.query(RubricAgentActivation).filter_by(agent_id="coordinator").one()
    )
    coord_act.rubric_set_id = coord_v1.rubric_set_id
    db_session.commit()

    # Re-resolving must reuse existing snapshots without consulting active pointer
    dtos_reused = resolve_or_reuse_evaluation_snapshots(db_session, eval_id, agents)
    assert dtos_reused == dtos_initial

    # Also verify with load_verified_evaluation_snapshots
    dtos_loaded = load_verified_evaluation_snapshots(db_session, eval_id, agents)
    assert dtos_loaded == dtos_initial


def test_reuse_proves_zero_activation_query_via_monkeypatch(db_session) -> None:
    _seed_all_rubrics(db_session)
    eval_id = _create_evaluation_job(db_session)

    agents = ("sme", "gad")
    dtos_initial = resolve_or_reuse_evaluation_snapshots(db_session, eval_id, agents)
    db_session.commit()

    # Monkeypatch loader to fail unconditionally
    with patch(
        "server.modules.rubrics.snapshots.load_active_form_definitions",
        side_effect=RuntimeError("Should not be called during reuse"),
    ):
        dtos_reused = resolve_or_reuse_evaluation_snapshots(db_session, eval_id, agents)
        assert dtos_reused == dtos_initial


def test_partial_existing_set_fails_without_inserting_missing(db_session) -> None:
    _seed_all_rubrics(db_session)
    eval_id = _create_evaluation_job(db_session)

    # Only create snapshot for SME
    resolve_or_reuse_evaluation_snapshots(db_session, eval_id, ("sme",))
    db_session.commit()

    initial_count = (
        db_session.query(EvaluationFormSnapshot)
        .filter_by(evaluation_id=eval_id)
        .count()
    )
    assert initial_count == 1

    # Requesting SME + GAD should fail because partial snapshot set exists
    with pytest.raises(SnapshotIntegrityError, match="snapshot set mismatch"):
        resolve_or_reuse_evaluation_snapshots(db_session, eval_id, ("sme", "gad"))

    # Ensure no rows were added
    after_count = (
        db_session.query(EvaluationFormSnapshot)
        .filter_by(evaluation_id=eval_id)
        .count()
    )
    assert after_count == 1


def test_extra_agent_in_existing_set_fails(db_session) -> None:
    _seed_all_rubrics(db_session)
    eval_id = _create_evaluation_job(db_session)

    # Create snapshots for SME and GAD
    resolve_or_reuse_evaluation_snapshots(db_session, eval_id, ("sme", "gad"))
    db_session.commit()

    # Requesting only SME must fail (extra snapshot exists in DB)
    with pytest.raises(SnapshotIntegrityError, match="snapshot set mismatch"):
        resolve_or_reuse_evaluation_snapshots(db_session, eval_id, ("sme",))

    with pytest.raises(SnapshotIntegrityError, match="snapshot set mismatch"):
        load_verified_evaluation_snapshots(db_session, eval_id, ("sme",))


def test_missing_evaluation_id_snapshots_fails_load(db_session) -> None:
    _seed_all_rubrics(db_session)
    eval_id = _create_evaluation_job(db_session)

    with pytest.raises(SnapshotIntegrityError, match="snapshot set mismatch"):
        load_verified_evaluation_snapshots(db_session, eval_id, ("sme",))


def test_payload_tampering_fails_verification(db_session) -> None:
    _seed_all_rubrics(db_session)
    eval_id = _create_evaluation_job(db_session)

    resolve_or_reuse_evaluation_snapshots(db_session, eval_id, ("sme",))
    db_session.commit()

    # Tamper with snapshot payload in DB
    row = (
        db_session.query(EvaluationFormSnapshot)
        .filter_by(evaluation_id=eval_id, agent_id="sme")
        .one()
    )
    tampered_payload = copy.deepcopy(row.snapshot_payload)
    tampered_payload["adapter_version"] = 99
    row.snapshot_payload = tampered_payload
    db_session.commit()

    with pytest.raises(SnapshotIntegrityError):
        load_verified_evaluation_snapshots(db_session, eval_id, ("sme",))

    with pytest.raises(SnapshotIntegrityError):
        resolve_or_reuse_evaluation_snapshots(db_session, eval_id, ("sme",))


def test_hash_tampering_fails_verification(db_session) -> None:
    _seed_all_rubrics(db_session)
    eval_id = _create_evaluation_job(db_session)

    resolve_or_reuse_evaluation_snapshots(db_session, eval_id, ("sme",))
    db_session.commit()

    row = (
        db_session.query(EvaluationFormSnapshot)
        .filter_by(evaluation_id=eval_id, agent_id="sme")
        .one()
    )
    row.snapshot_hash = "0" * 64
    db_session.commit()

    with pytest.raises(SnapshotIntegrityError):
        load_verified_evaluation_snapshots(db_session, eval_id, ("sme",))

    with pytest.raises(SnapshotIntegrityError):
        resolve_or_reuse_evaluation_snapshots(db_session, eval_id, ("sme",))


def test_column_tampering_fails_verification(db_session) -> None:
    _seed_all_rubrics(db_session)
    eval_id = _create_evaluation_job(db_session)

    resolve_or_reuse_evaluation_snapshots(db_session, eval_id, ("sme",))
    db_session.commit()

    row = (
        db_session.query(EvaluationFormSnapshot)
        .filter_by(evaluation_id=eval_id, agent_id="sme")
        .one()
    )
    row.adapter_key = "tampered_adapter"
    db_session.commit()

    with pytest.raises(SnapshotIntegrityError):
        load_verified_evaluation_snapshots(db_session, eval_id, ("sme",))


def test_sqlite_conflict_path_concurrent_duplicate_insert(db_session) -> None:
    _seed_all_rubrics(db_session)
    eval_id = _create_evaluation_job(db_session)

    orig_loader = load_active_form_definitions
    winner_snapshot_id = uuid.uuid4()

    def concurrent_loader(session, scheduled_agents):
        forms = orig_loader(session, scheduled_agents)
        # Concurrently build and insert an identical-payload snapshot
        winner_dto = build_evaluation_form_snapshot(
            evaluation_id=eval_id,
            form=forms["sme"],
            snapshot_id=winner_snapshot_id,
        )
        session.add(
            EvaluationFormSnapshot(
                snapshot_id=winner_dto.snapshot_id,
                evaluation_id=winner_dto.evaluation_id,
                agent_id=winner_dto.agent_id,
                rubric_set_id=winner_dto.rubric_set_id,
                snapshot_payload=winner_dto.snapshot_payload.model_dump(mode="json"),
                snapshot_hash=winner_dto.snapshot_hash,
                adapter_key=winner_dto.adapter_key,
                adapter_version=winner_dto.adapter_version,
            )
        )
        session.flush()
        return forms

    with patch(
        "server.modules.rubrics.snapshots.load_active_form_definitions",
        side_effect=concurrent_loader,
    ):
        dtos = resolve_or_reuse_evaluation_snapshots(db_session, eval_id, ("sme",))

    # Resolution succeeds via DO NOTHING, readback has winner_snapshot_id
    assert len(dtos) == 1
    assert dtos[0].snapshot_id == winner_snapshot_id

    # Exactly 1 row in the database
    rows = (
        db_session.query(EvaluationFormSnapshot).filter_by(evaluation_id=eval_id).all()
    )
    assert len(rows) == 1
    assert rows[0].snapshot_id == winner_snapshot_id


def test_sqlite_conflict_mismatch_fails_and_leaves_no_rows(db_session) -> None:
    _seed_all_rubrics(db_session)
    eval_id = _create_evaluation_job(db_session)

    orig_loader = load_active_form_definitions

    def conflicting_mismatch_loader(session, scheduled_agents):
        forms = orig_loader(session, scheduled_agents)
        # Build snapshot for a different rubric set / payload
        other_form = orig_loader(session, ("gad",))["gad"]
        # Fake payload with SME agent_id but different rubric_set_id
        winner_dto = build_evaluation_form_snapshot(
            evaluation_id=eval_id,
            form=other_form,
        )
        session.add(
            EvaluationFormSnapshot(
                snapshot_id=winner_dto.snapshot_id,
                evaluation_id=eval_id,
                agent_id="sme",
                rubric_set_id=winner_dto.rubric_set_id,
                snapshot_payload=winner_dto.snapshot_payload.model_dump(mode="json"),
                snapshot_hash=winner_dto.snapshot_hash,
                adapter_key="sme",
                adapter_version=1,
            )
        )
        session.flush()
        return forms

    with patch(
        "server.modules.rubrics.snapshots.load_active_form_definitions",
        side_effect=conflicting_mismatch_loader,
    ):
        with pytest.raises(SnapshotIntegrityError):
            resolve_or_reuse_evaluation_snapshots(db_session, eval_id, ("sme",))

    db_session.rollback()
    count = (
        db_session.query(EvaluationFormSnapshot)
        .filter_by(evaluation_id=eval_id)
        .count()
    )
    assert count == 0


def test_deployed_budget_exceeded_rejection_fresh_and_reuse(db_session) -> None:
    _seed_all_rubrics(db_session)
    eval_id = _create_evaluation_job(db_session)

    # 1. Fresh creation failure with low prompt budget
    low_budget_settings = MagicMock()
    low_budget_settings.sme_total_prompt_budget_chars = 10
    low_budget_settings.coordinator_total_prompt_budget_chars = 10
    low_budget_settings.gad_total_prompt_budget_chars = 10
    low_budget_settings.itso_total_prompt_budget_chars = 10

    with patch(
        "server.modules.rubrics.repository.get_settings",
        return_value=low_budget_settings,
    ):
        with pytest.raises(SnapshotIntegrityError):
            resolve_or_reuse_evaluation_snapshots(db_session, eval_id, ("sme",))

    # Verify no partial rows persisted
    count = (
        db_session.query(EvaluationFormSnapshot)
        .filter_by(evaluation_id=eval_id)
        .count()
    )
    assert count == 0

    # 2. Existing snapshot reuse/load rejection when budget setting is lowered later
    resolve_or_reuse_evaluation_snapshots(db_session, eval_id, ("sme",))
    db_session.commit()

    with patch(
        "server.modules.rubrics.repository.get_settings",
        return_value=low_budget_settings,
    ):
        with pytest.raises(SnapshotIntegrityError, match="deployed budget validation"):
            load_verified_evaluation_snapshots(db_session, eval_id, ("sme",))

        with pytest.raises(SnapshotIntegrityError, match="deployed budget validation"):
            resolve_or_reuse_evaluation_snapshots(db_session, eval_id, ("sme",))


def test_transaction_rollback_leaves_zero_rows(db_session) -> None:
    _seed_all_rubrics(db_session)
    eval_id = _create_evaluation_job(db_session)

    # Resolve without commit, then rollback
    resolve_or_reuse_evaluation_snapshots(db_session, eval_id, ("sme", "gad"))
    db_session.rollback()

    count = (
        db_session.query(EvaluationFormSnapshot)
        .filter_by(evaluation_id=eval_id)
        .count()
    )
    assert count == 0


def test_input_validation_empty_duplicate_unknown_agents(db_session) -> None:
    _seed_all_rubrics(db_session)
    eval_id = _create_evaluation_job(db_session)

    with pytest.raises(SnapshotIntegrityError, match="non-string sequence"):
        resolve_or_reuse_evaluation_snapshots(
            db_session,
            eval_id,
            "sme",  # type: ignore[arg-type]
        )

    with pytest.raises(SnapshotIntegrityError, match="non-string sequence"):
        resolve_or_reuse_evaluation_snapshots(
            db_session,
            eval_id,
            b"sme",  # type: ignore[arg-type]
        )

    with pytest.raises(SnapshotIntegrityError, match="cannot be empty"):
        resolve_or_reuse_evaluation_snapshots(db_session, eval_id, ())

    with pytest.raises(SnapshotIntegrityError, match="Duplicate agent ID"):
        resolve_or_reuse_evaluation_snapshots(db_session, eval_id, ("sme", "sme"))

    with pytest.raises(SnapshotIntegrityError, match="Unknown scheduled agent"):
        resolve_or_reuse_evaluation_snapshots(
            db_session, eval_id, ("sme", "invalid_agent")
        )

    long_agent = "x" * 100
    with pytest.raises(SnapshotIntegrityError, match="maximum code length"):
        resolve_or_reuse_evaluation_snapshots(db_session, eval_id, ("sme", long_agent))

    with pytest.raises(SnapshotIntegrityError, match="must be a valid UUID"):
        resolve_or_reuse_evaluation_snapshots(
            db_session,
            "not-a-uuid",
            ("sme",),  # type: ignore[arg-type]
        )


def test_unsupported_dialect_raises_snapshot_integrity_error(db_session) -> None:
    _seed_all_rubrics(db_session)
    eval_id = _create_evaluation_job(db_session)

    with patch.object(db_session.get_bind().dialect, "name", "oracle"):
        with pytest.raises(
            SnapshotIntegrityError, match="Unsupported database dialect"
        ):
            resolve_or_reuse_evaluation_snapshots(db_session, eval_id, ("sme",))


# ---------------------------------------------------------------------------
# Orchestrator Preparation Seam & Verification Tests
# ---------------------------------------------------------------------------


def test_prepare_snapshots_and_enter_evaluating_atomic_success_full(
    db_session,
) -> None:
    _seed_all_rubrics(db_session)
    eval_id = _create_evaluation_job(db_session)
    token = uuid.uuid4()

    job = db_session.get(EvaluationJob, eval_id)
    job.status = EvaluationStatus.PREPROCESSING.value
    job.admission_slot = 1
    job.execution_token = token
    db_session.commit()

    from server.modules.evaluations.agent_schedule import scheduled_agent_ids
    from server.modules.evaluations.orchestrator import (
        _prepare_snapshots_and_enter_evaluating,
    )
    from server.modules.rubrics.snapshot_contracts import EvaluationFormSnapshotDTO

    scheduled_ids = scheduled_agent_ids(partial_without_curriculum=False)
    assert scheduled_ids == ("sme", "coordinator", "gad", "itso")

    returned_snapshots = _prepare_snapshots_and_enter_evaluating(
        db_session,
        eval_id,
        token,
        scheduled_ids,
        reuse_only=False,
    )

    assert isinstance(returned_snapshots, tuple)
    assert len(returned_snapshots) == 4
    assert tuple(s.agent_id for s in returned_snapshots) == (
        "sme",
        "coordinator",
        "gad",
        "itso",
    )
    assert all(isinstance(s, EvaluationFormSnapshotDTO) for s in returned_snapshots)

    db_session.expire_all()
    refreshed = db_session.get(EvaluationJob, eval_id)
    assert refreshed.status == EvaluationStatus.EVALUATING.value

    rows = (
        db_session.query(EvaluationFormSnapshot).filter_by(evaluation_id=eval_id).all()
    )
    assert len(rows) == 4
    assert {r.agent_id for r in rows} == {"sme", "coordinator", "gad", "itso"}


def test_prepare_snapshots_and_enter_evaluating_atomic_success_partial(
    db_session,
) -> None:
    _seed_all_rubrics(db_session)
    eval_id = _create_evaluation_job(db_session)
    token = uuid.uuid4()

    job = db_session.get(EvaluationJob, eval_id)
    job.status = EvaluationStatus.PREPROCESSING.value
    job.admission_slot = 1
    job.execution_token = token
    job.partial_without_curriculum = True
    db_session.commit()

    from server.modules.evaluations.agent_schedule import scheduled_agent_ids
    from server.modules.evaluations.orchestrator import (
        _prepare_snapshots_and_enter_evaluating,
    )
    from server.modules.rubrics.snapshot_contracts import EvaluationFormSnapshotDTO

    scheduled_ids = scheduled_agent_ids(partial_without_curriculum=True)
    assert scheduled_ids == ("sme", "gad", "itso")

    returned_snapshots = _prepare_snapshots_and_enter_evaluating(
        db_session,
        eval_id,
        token,
        scheduled_ids,
        reuse_only=False,
    )

    assert isinstance(returned_snapshots, tuple)
    assert len(returned_snapshots) == 3
    assert tuple(s.agent_id for s in returned_snapshots) == ("sme", "gad", "itso")
    assert all(isinstance(s, EvaluationFormSnapshotDTO) for s in returned_snapshots)

    db_session.expire_all()
    refreshed = db_session.get(EvaluationJob, eval_id)
    assert refreshed.status == EvaluationStatus.EVALUATING.value

    rows = (
        db_session.query(EvaluationFormSnapshot).filter_by(evaluation_id=eval_id).all()
    )
    assert len(rows) == 3
    assert {r.agent_id for r in rows} == {"sme", "gad", "itso"}


def test_prepare_snapshots_rollback_leaves_zero_snapshots_and_preprocessing(
    db_session,
) -> None:
    _seed_all_rubrics(db_session)
    eval_id = _create_evaluation_job(db_session)
    token = uuid.uuid4()

    job = db_session.get(EvaluationJob, eval_id)
    job.status = EvaluationStatus.PREPROCESSING.value
    job.admission_slot = 1
    job.execution_token = token
    db_session.commit()

    from server.modules.evaluations.agent_schedule import scheduled_agent_ids
    from server.modules.evaluations.orchestrator import (
        _prepare_snapshots_and_enter_evaluating,
    )

    scheduled_ids = scheduled_agent_ids(partial_without_curriculum=False)

    # Invalidate one active rubric set so resolution fails during candidate building
    db_session.query(RubricAgentActivation).filter_by(agent_id="gad").delete()
    db_session.commit()

    with pytest.raises(SnapshotIntegrityError):
        _prepare_snapshots_and_enter_evaluating(
            db_session,
            eval_id,
            token,
            scheduled_ids,
            reuse_only=False,
        )

    db_session.expire_all()
    refreshed = db_session.get(EvaluationJob, eval_id)
    assert refreshed.status == EvaluationStatus.PREPROCESSING.value

    count = (
        db_session.query(EvaluationFormSnapshot)
        .filter_by(evaluation_id=eval_id)
        .count()
    )
    assert count == 0


def test_prepare_snapshots_commit_failure_rolls_back_everything(
    db_session,
) -> None:
    _seed_all_rubrics(db_session)
    eval_id = _create_evaluation_job(db_session)
    token = uuid.uuid4()

    job = db_session.get(EvaluationJob, eval_id)
    job.status = EvaluationStatus.PREPROCESSING.value
    job.admission_slot = 1
    job.execution_token = token
    db_session.commit()

    from server.modules.evaluations.agent_schedule import scheduled_agent_ids
    from server.modules.evaluations.orchestrator import (
        _prepare_snapshots_and_enter_evaluating,
    )

    scheduled_ids = scheduled_agent_ids(partial_without_curriculum=False)

    original_commit = db_session.commit

    def failing_commit():
        raise RuntimeError("Injected database commit failure")

    db_session.commit = failing_commit
    try:
        with pytest.raises(RuntimeError, match="Injected database commit failure"):
            _prepare_snapshots_and_enter_evaluating(
                db_session,
                eval_id,
                token,
                scheduled_ids,
                reuse_only=False,
            )
    finally:
        db_session.commit = original_commit

    db_session.expire_all()
    refreshed = db_session.get(EvaluationJob, eval_id)
    assert refreshed.status == EvaluationStatus.PREPROCESSING.value

    count = (
        db_session.query(EvaluationFormSnapshot)
        .filter_by(evaluation_id=eval_id)
        .count()
    )
    assert count == 0


def test_prepare_snapshots_ownership_or_status_loss_fails_closed(
    db_session,
) -> None:
    _seed_all_rubrics(db_session)
    eval_id = _create_evaluation_job(db_session)
    token = uuid.uuid4()
    wrong_token = uuid.uuid4()

    job = db_session.get(EvaluationJob, eval_id)
    job.status = EvaluationStatus.PREPROCESSING.value
    job.admission_slot = 1
    job.execution_token = token
    db_session.commit()

    from server.modules.evaluations.agent_schedule import scheduled_agent_ids
    from server.modules.evaluations.exceptions import EvaluationExecutionOwnershipError
    from server.modules.evaluations.orchestrator import (
        _prepare_snapshots_and_enter_evaluating,
    )

    scheduled_ids = scheduled_agent_ids(partial_without_curriculum=False)

    # 1. Wrong token
    with pytest.raises(EvaluationExecutionOwnershipError):
        _prepare_snapshots_and_enter_evaluating(
            db_session,
            eval_id,
            wrong_token,
            scheduled_ids,
            reuse_only=False,
        )

    # 2. Wrong status (e.g. SUBMITTED or already EVALUATING)
    job.status = EvaluationStatus.SUBMITTED.value
    db_session.commit()
    with pytest.raises(EvaluationExecutionOwnershipError):
        _prepare_snapshots_and_enter_evaluating(
            db_session,
            eval_id,
            token,
            scheduled_ids,
            reuse_only=False,
        )

    # 3. Admission slot != 1
    job.status = EvaluationStatus.PREPROCESSING.value
    job.admission_slot = None
    db_session.commit()
    with pytest.raises(EvaluationExecutionOwnershipError):
        _prepare_snapshots_and_enter_evaluating(
            db_session,
            eval_id,
            token,
            scheduled_ids,
            reuse_only=False,
        )

    count = (
        db_session.query(EvaluationFormSnapshot)
        .filter_by(evaluation_id=eval_id)
        .count()
    )
    assert count == 0


def test_prepare_snapshots_reuse_only_with_missing_snapshots_fails_without_resolving(
    db_session,
) -> None:
    _seed_all_rubrics(db_session)
    eval_id = _create_evaluation_job(db_session)
    token = uuid.uuid4()

    job = db_session.get(EvaluationJob, eval_id)
    job.status = EvaluationStatus.PREPROCESSING.value
    job.admission_slot = 1
    job.execution_token = token
    db_session.commit()

    from server.modules.evaluations.agent_schedule import scheduled_agent_ids
    from server.modules.evaluations.orchestrator import (
        _prepare_snapshots_and_enter_evaluating,
    )

    scheduled_ids = scheduled_agent_ids(partial_without_curriculum=False)

    # reuse_only=True with missing snapshots fails closed with SnapshotIntegrityError
    with pytest.raises(SnapshotIntegrityError):
        _prepare_snapshots_and_enter_evaluating(
            db_session,
            eval_id,
            token,
            scheduled_ids,
            reuse_only=True,
        )

    db_session.expire_all()
    refreshed = db_session.get(EvaluationJob, eval_id)
    assert refreshed.status == EvaluationStatus.PREPROCESSING.value

    count = (
        db_session.query(EvaluationFormSnapshot)
        .filter_by(evaluation_id=eval_id)
        .count()
    )
    assert count == 0


def test_prepare_snapshots_recovery_no_results_reuses_snapshots_despite_active_change(
    db_session,
) -> None:
    _seed_all_rubrics(db_session)
    eval_id = _create_evaluation_job(db_session)
    token = uuid.uuid4()

    job = db_session.get(EvaluationJob, eval_id)
    job.status = EvaluationStatus.PREPROCESSING.value
    job.admission_slot = 1
    job.execution_token = token
    db_session.commit()

    from server.modules.evaluations.agent_schedule import scheduled_agent_ids
    from server.modules.evaluations.orchestrator import (
        _prepare_snapshots_and_enter_evaluating,
    )

    scheduled_ids = scheduled_agent_ids(partial_without_curriculum=False)

    # Step 1: Initial preparation creates snapshots
    _prepare_snapshots_and_enter_evaluating(
        db_session,
        eval_id,
        token,
        scheduled_ids,
        reuse_only=False,
    )

    orig_snapshots = (
        db_session.query(EvaluationFormSnapshot).filter_by(evaluation_id=eval_id).all()
    )
    orig_hashes = {s.agent_id: s.snapshot_hash for s in orig_snapshots}
    assert len(orig_hashes) == 4

    # Step 2: Now simulate a recovery restart where status got reset to PREPROCESSING
    # and active rubric set changed or was unpublished
    job = db_session.get(EvaluationJob, eval_id)
    job.status = EvaluationStatus.PREPROCESSING.value
    new_token = uuid.uuid4()
    job.execution_token = new_token
    db_session.commit()

    # Delete activation for GAD
    db_session.query(RubricAgentActivation).filter_by(agent_id="gad").delete()
    db_session.commit()

    # Recovery without results reuses snapshots without looking up active forms
    reused_returned_snapshots = _prepare_snapshots_and_enter_evaluating(
        db_session,
        eval_id,
        new_token,
        scheduled_ids,
        reuse_only=False,
    )

    assert isinstance(reused_returned_snapshots, tuple)
    assert tuple(s.agent_id for s in reused_returned_snapshots) == (
        "sme",
        "coordinator",
        "gad",
        "itso",
    )
    assert {
        s.agent_id: s.snapshot_hash for s in reused_returned_snapshots
    } == orig_hashes

    db_session.expire_all()
    refreshed = db_session.get(EvaluationJob, eval_id)
    assert refreshed.status == EvaluationStatus.EVALUATING.value

    reused_snapshots = (
        db_session.query(EvaluationFormSnapshot).filter_by(evaluation_id=eval_id).all()
    )
    reused_hashes = {s.agent_id: s.snapshot_hash for s in reused_snapshots}
    assert reused_hashes == orig_hashes


def test_supervisor_construction_agent_order_and_terminal_validation(
    db_session,
) -> None:
    from server.modules.evaluations.agent_schedule import (
        FULL_SCHEDULED_AGENT_IDS,
        PARTIAL_WITHOUT_CURRICULUM_SCHEDULED_AGENT_IDS,
        scheduled_agent_ids,
    )
    from server.modules.evaluations.orchestrator import (
        _build_supervisor_agents,
        _validate_required_agent_results,
    )
    from server.modules.synthesis.models import AgentResult

    # Verify scheduled_agent_ids pure contract
    assert (
        scheduled_agent_ids(partial_without_curriculum=False)
        == FULL_SCHEDULED_AGENT_IDS
    )
    assert scheduled_agent_ids(partial_without_curriculum=True) == (
        PARTIAL_WITHOUT_CURRICULUM_SCHEDULED_AGENT_IDS
    )
    assert FULL_SCHEDULED_AGENT_IDS == ("sme", "coordinator", "gad", "itso")
    assert PARTIAL_WITHOUT_CURRICULUM_SCHEDULED_AGENT_IDS == ("sme", "gad", "itso")

    # Verify _build_supervisor_agents factory mapping and order
    full_agents = _build_supervisor_agents(FULL_SCHEDULED_AGENT_IDS)
    assert [a.agent_name for a in full_agents] == ["sme", "coordinator", "gad", "itso"]

    partial_agents = _build_supervisor_agents(
        PARTIAL_WITHOUT_CURRICULUM_SCHEDULED_AGENT_IDS
    )
    assert [a.agent_name for a in partial_agents] == ["sme", "gad", "itso"]

    # Verify terminal validation with helper
    full_results = [
        AgentResult(agent_name=name, success=True) for name in FULL_SCHEDULED_AGENT_IDS
    ]
    assert (
        _validate_required_agent_results(
            full_results,
            partial_without_curriculum=False,
            curriculum_available=True,
        )
        is None
    )

    # Missing coordinator in full
    partial_results = [
        AgentResult(agent_name=name, success=True)
        for name in PARTIAL_WITHOUT_CURRICULUM_SCHEDULED_AGENT_IDS
    ]
    err = _validate_required_agent_results(
        partial_results,
        partial_without_curriculum=False,
        curriculum_available=True,
    )
    assert err is not None
    assert "coordinator" in err.lower()

    # Partial without curriculum accepts partial results
    assert (
        _validate_required_agent_results(
            partial_results,
            partial_without_curriculum=True,
            curriculum_available=False,
        )
        is None
    )


# ---------------------------------------------------------------------------
# Production Path Orchestrator Regressions
# ---------------------------------------------------------------------------


def test_execute_claimed_evaluation_fails_before_supervisor_on_missing_snapshot(
    db_session, monkeypatch
) -> None:
    """Missing active form aborts before supervisor construction/dispatch."""
    from server.core import database as core_database
    from server.modules.evaluations.exceptions import EvaluationPipelineFailure
    from server.modules.evaluations.orchestrator import _execute_claimed_evaluation
    from sqlalchemy.orm import sessionmaker

    _seed_all_rubrics(db_session)
    eval_id = _create_evaluation_job(db_session)

    # Delete activation for GAD so preparation fails
    db_session.query(RubricAgentActivation).filter_by(agent_id="gad").delete()
    db_session.commit()

    session_factory = sessionmaker(
        bind=db_session.get_bind(), autoflush=False, autocommit=False
    )
    monkeypatch.setattr(core_database, "get_session_factory", lambda: session_factory)

    # Track if supervisor factory/run is ever touched
    supervisor_constructed = False
    run_called = False

    def fake_build(*args, **kwargs):
        nonlocal supervisor_constructed
        supervisor_constructed = True
        raise AssertionError("_build_supervisor_agents should not be reached")

    def fake_run(*args, **kwargs):
        nonlocal run_called
        run_called = True
        raise AssertionError("Supervisor.run_evaluation should not be reached")

    monkeypatch.setattr(
        "server.modules.evaluations.orchestrator._build_supervisor_agents",
        fake_build,
    )
    monkeypatch.setattr(
        "server.modules.evaluations.orchestrator.Supervisor.run_evaluation",
        fake_run,
    )

    token = uuid.uuid4()
    with session_factory() as session:
        job = session.get(EvaluationJob, eval_id)
        job.status = EvaluationStatus.PREPROCESSING.value
        job.admission_slot = 1
        job.execution_token = token
        job.partial_without_curriculum = True
        session.commit()

    with pytest.raises(EvaluationPipelineFailure):
        _execute_claimed_evaluation(
            eval_id,
            execution_token=token,
            db_session_factory=session_factory,
        )

    assert not supervisor_constructed
    assert not run_called

    # Verify job ends FAILED and no partial snapshot rows were committed
    with session_factory() as session:
        refreshed = session.get(EvaluationJob, eval_id)
        assert refreshed.status == EvaluationStatus.FAILED.value
        count = (
            session.query(EvaluationFormSnapshot)
            .filter_by(evaluation_id=eval_id)
            .count()
        )
        assert count == 0


def test_execute_claimed_evaluation_existing_results_missing_snapshots_uses_reuse_only(
    db_session, monkeypatch
) -> None:
    """Existing results with missing snapshots uses reuse-only and skips supervisor."""
    from server.core import database as core_database
    from server.modules.evaluations.exceptions import EvaluationPipelineFailure
    from server.modules.evaluations.orchestrator import _execute_claimed_evaluation
    from server.modules.synthesis.models import AgentResult
    from sqlalchemy.orm import sessionmaker

    _seed_all_rubrics(db_session)
    eval_id = _create_evaluation_job(db_session)

    session_factory = sessionmaker(
        bind=db_session.get_bind(), autoflush=False, autocommit=False
    )
    monkeypatch.setattr(core_database, "get_session_factory", lambda: session_factory)

    # Insert an existing AgentResult row without creating snapshots
    token = uuid.uuid4()
    with session_factory() as session:
        job = session.get(EvaluationJob, eval_id)
        job.status = EvaluationStatus.PREPROCESSING.value
        job.admission_slot = 1
        job.execution_token = token
        job.partial_without_curriculum = True
        session.add(
            AgentResult(
                agent_result_id=uuid.uuid4(),
                evaluation_id=eval_id,
                document_id=job.document_id,
                agent_name="sme",
                subtotal=3.0,
                processing_seconds=0.1,
                token_count=10,
                model_name="test-model",
                summary="ok",
                success=True,
            )
        )
        session.commit()

    # Active-form loader should NEVER be called when reuse_only is True
    active_forms_called = False

    def fake_load_active(*args, **kwargs):
        nonlocal active_forms_called
        active_forms_called = True
        raise AssertionError("load_active_form_definitions called for reuse_only")

    monkeypatch.setattr(
        "server.modules.rubrics.snapshots.load_active_form_definitions",
        fake_load_active,
    )

    # Supervisor should NEVER be called
    supervisor_called = False

    def fake_run(*args, **kwargs):
        nonlocal supervisor_called
        supervisor_called = True
        raise AssertionError("Supervisor.run_evaluation must not be called")

    monkeypatch.setattr(
        "server.modules.evaluations.orchestrator.Supervisor.run_evaluation",
        fake_run,
    )

    with pytest.raises(EvaluationPipelineFailure):
        _execute_claimed_evaluation(
            eval_id,
            execution_token=token,
            db_session_factory=session_factory,
        )

    assert not active_forms_called
    assert not supervisor_called

    with session_factory() as session:
        refreshed = session.get(EvaluationJob, eval_id)
        assert refreshed.status == EvaluationStatus.FAILED.value
        count = (
            session.query(EvaluationFormSnapshot)
            .filter_by(evaluation_id=eval_id)
            .count()
        )
        assert count == 0
