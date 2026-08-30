"""Tests for dynamic CID rubric models, constraints, and repository primitives."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.rubrics.contracts import FormDefinition
from server.modules.rubrics.models import (
    EvaluationFormSnapshot,
    RubricAgentActivation,
    RubricCriterion,
    RubricDomain,
    RubricSet,
)
from server.modules.rubrics.repository import (
    activate_revision,
    create_draft_from_active,
    delete_draft_revision,
    get_active_form_definition,
    get_form_definition_by_id,
    lock_draft_rubric_set,
    publish_draft_revision,
    retire_revision,
)
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError, IntegrityError


@pytest.fixture()
def test_admin_user(db_session):
    user = create_user(
        db_session,
        name="Admin Test",
        email=f"admin_{uuid.uuid4().hex[:8]}@example.com",
        password="password123",
        role=UserRole.ADMIN,
    )
    db_session.commit()
    return user


def _create_published_sme_v1(
    db_session, actor_id: uuid.UUID | None = None
) -> RubricSet:
    now = datetime.now(UTC)
    rubric_set = RubricSet(
        rubric_set_id=uuid.uuid4(),
        agent_id="sme",
        name="SME Rubric v1",
        version_number=1,
        status="published",
        adapter_key="sme",
        adapter_version=1,
        published_at=now,
        published_by=actor_id,
        created_at=now,
    )
    db_session.add(rubric_set)
    db_session.flush()

    domain = RubricDomain(
        rubric_domain_id=uuid.uuid4(),
        rubric_set_id=rubric_set.rubric_set_id,
        code="OP",
        title="Organization & Presentation",
        display_order=1,
    )
    db_session.add(domain)
    db_session.flush()

    criterion = RubricCriterion(
        rubric_criterion_id=uuid.uuid4(),
        rubric_domain_id=domain.rubric_domain_id,
        criterion_code="OP-02",
        title="Interactivity",
        description="Material is interactive in each lesson.",
        scoring_rule="Count interactive elements: 4+ -> 4, 2-3 -> 3, 1 -> 2, 0 -> 1.",
        scoring_strategy="count_band",
        strategy_config={
            "strategy": "count_band",
            "mode": "minimum_count",
            "threshold_4": 4,
            "threshold_3": 2,
            "threshold_2": 1,
        },
        display_order=1,
    )
    db_session.add(criterion)
    db_session.flush()

    activation = RubricAgentActivation(
        agent_id="sme",
        rubric_set_id=rubric_set.rubric_set_id,
        updated_by=actor_id,
        updated_at=now,
    )
    db_session.add(activation)
    db_session.commit()
    return rubric_set


# ---------------------------------------------------------------------------
# ORM & Schema Constraint Tests
# ---------------------------------------------------------------------------


def test_rubric_set_status_check_constraint(db_session):
    """Status must be draft, published, or retired."""
    invalid_set = RubricSet(
        rubric_set_id=uuid.uuid4(),
        agent_id="sme",
        name="Invalid Status Rubric",
        version_number=99,
        status="invalid_status",
        adapter_key="sme",
        adapter_version=1,
    )
    db_session.add(invalid_set)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_rubric_set_one_draft_per_agent_constraint(db_session):
    """At most one draft revision per agent may exist."""
    draft_1 = RubricSet(
        rubric_set_id=uuid.uuid4(),
        agent_id="gad",
        name="GAD Draft 1",
        version_number=2,
        status="draft",
        adapter_key="gad",
        adapter_version=1,
    )
    db_session.add(draft_1)
    db_session.commit()

    draft_2 = RubricSet(
        rubric_set_id=uuid.uuid4(),
        agent_id="gad",
        name="GAD Draft 2",
        version_number=3,
        status="draft",
        adapter_key="gad",
        adapter_version=1,
    )
    db_session.add(draft_2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_rubric_agent_activation_composite_fk_enforces_same_agent(db_session):
    """Activation composite FK rejects mismatched agent_id target."""
    db_session.execute(text("PRAGMA foreign_keys=ON"))
    sme_set = _create_published_sme_v1(db_session)

    # Attempt to activate sme_set under agent_id='gad'
    mismatched_activation = RubricAgentActivation(
        agent_id="gad",
        rubric_set_id=sme_set.rubric_set_id,
        updated_by=None,
        updated_at=datetime.now(UTC),
    )
    db_session.add(mismatched_activation)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_evaluation_form_snapshot_uniqueness_per_evaluation_agent(
    db_session, test_admin_user
):
    """UNIQUE(evaluation_id, agent_id) is enforced on snapshots."""
    from server.modules.documents.models import Document
    from server.modules.evaluations.models import EvaluationJob

    doc = Document(
        document_id=uuid.uuid4(),
        title="Test SLM",
        file_path="/tmp/test.pdf",
        source_type="slm",
        uploaded_by=test_admin_user.user_id,
    )
    db_session.add(doc)
    db_session.flush()

    job = EvaluationJob(
        evaluation_id=uuid.uuid4(),
        document_id=doc.document_id,
        status="EVALUATING",
    )
    db_session.add(job)
    db_session.flush()

    sme_set = _create_published_sme_v1(db_session)

    snap1 = EvaluationFormSnapshot(
        snapshot_id=uuid.uuid4(),
        evaluation_id=job.evaluation_id,
        agent_id="sme",
        rubric_set_id=sme_set.rubric_set_id,
        snapshot_payload={"form": "data"},
        snapshot_hash="a" * 64,
        adapter_key="sme",
        adapter_version=1,
    )
    db_session.add(snap1)
    db_session.commit()

    snap2 = EvaluationFormSnapshot(
        snapshot_id=uuid.uuid4(),
        evaluation_id=job.evaluation_id,
        agent_id="sme",
        rubric_set_id=sme_set.rubric_set_id,
        snapshot_payload={"form": "data2"},
        snapshot_hash="b" * 64,
        adapter_key="sme",
        adapter_version=1,
    )
    db_session.add(snap2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# ---------------------------------------------------------------------------
# Pure ORM -> FormDefinition & Active Pointer Tests
# ---------------------------------------------------------------------------


def test_orm_to_form_definition_canonical_and_validated(db_session):
    """Conversion validates strategy configs and canonicalizes ordering."""
    _create_published_sme_v1(db_session)
    form_def = get_active_form_definition(db_session, "sme")

    assert form_def is not None
    assert isinstance(form_def, FormDefinition)
    assert form_def.agent_id == "sme"
    assert form_def.version_number == 1
    assert len(form_def.domains) == 1
    assert form_def.domains[0].code == "OP"
    assert len(form_def.domains[0].criteria) == 1
    crit = form_def.domains[0].criteria[0]
    assert crit.criterion_code == "OP-02"
    assert crit.strategy_config.strategy == "count_band"


def test_orm_to_form_definition_fails_on_missing_strategy_config(db_session):
    """Conversion rejects criteria without strategy_config."""
    sme_set = _create_published_sme_v1(db_session)
    crit = db_session.query(RubricCriterion).filter_by(criterion_code="OP-02").one()
    crit.strategy_config = None
    db_session.flush()

    with pytest.raises(ValueError, match="missing required strategy_config"):
        get_form_definition_by_id(db_session, sme_set.rubric_set_id)


def test_orm_to_form_definition_fails_on_mismatched_scoring_strategy(db_session):
    """Conversion rejects criteria where strategy does not match config."""
    sme_set = _create_published_sme_v1(db_session)
    crit = db_session.query(RubricCriterion).filter_by(criterion_code="OP-02").one()
    crit.scoring_strategy = "ratio_band"  # but config is count_band
    db_session.flush()

    with pytest.raises(ValueError, match="does not match strategy_config"):
        get_form_definition_by_id(db_session, sme_set.rubric_set_id)


def test_get_active_form_definition_fails_closed_on_invalid_status(db_session):
    """Active pointer pointing to draft or retired revision raises ValueError."""
    sme_set = _create_published_sme_v1(db_session)
    sme_set.status = "retired"
    db_session.flush()

    with pytest.raises(ValueError, match="has invalid status 'retired'"):
        get_active_form_definition(db_session, "sme")


def test_activate_revision_requires_existing_activation_for_admin(
    db_session, test_admin_user
):
    """Normal admin activation requires pre-existing activation pointer."""
    now = datetime.now(UTC)
    new_set = RubricSet(
        rubric_set_id=uuid.uuid4(),
        agent_id="gad",
        name="GAD Rubric",
        version_number=1,
        status="published",
        adapter_key="gad",
        adapter_version=1,
        published_at=now,
        created_at=now,
    )
    db_session.add(new_set)
    db_session.commit()

    with pytest.raises(ValueError, match="no existing activation pointer"):
        activate_revision(
            db_session, "gad", new_set.rubric_set_id, actor_id=test_admin_user.user_id
        )


def test_lock_activation_and_revisions_includes_active_revision(db_session):
    """lock_activation_and_revisions includes current active revision in lock set."""
    from server.modules.rubrics.repository import lock_activation_and_revisions

    sme_set = _create_published_sme_v1(db_session)
    other_id = uuid.uuid4()

    activation, revisions = lock_activation_and_revisions(db_session, "sme", [other_id])
    assert activation is not None
    assert any(r.rubric_set_id == sme_set.rubric_set_id for r in revisions)


def test_evaluation_form_snapshot_immutability_trigger(db_session, test_admin_user):
    """Database trigger rejects update or delete of evaluation_form_snapshots."""
    from server.modules.documents.models import Document
    from server.modules.evaluations.models import EvaluationJob
    from sqlalchemy import delete, update

    # Install SQLite immutability trigger for this test database session
    db_session.execute(
        text(
            """
            CREATE TRIGGER IF NOT EXISTS trg_eval_snapshots_no_update_test
            BEFORE UPDATE ON evaluation_form_snapshots
            BEGIN
                SELECT RAISE(FAIL, 'evaluation_form_snapshots rows are immutable');
            END;
            """
        )
    )
    db_session.execute(
        text(
            """
            CREATE TRIGGER IF NOT EXISTS trg_eval_snapshots_no_delete_test
            BEFORE DELETE ON evaluation_form_snapshots
            BEGIN
                SELECT RAISE(FAIL, 'evaluation_form_snapshots rows are immutable');
            END;
            """
        )
    )
    db_session.commit()

    doc = Document(
        document_id=uuid.uuid4(),
        title="Test SLM Immutability",
        file_path="/tmp/test.pdf",
        source_type="slm",
        uploaded_by=test_admin_user.user_id,
    )
    db_session.add(doc)
    db_session.flush()

    job = EvaluationJob(
        evaluation_id=uuid.uuid4(),
        document_id=doc.document_id,
        status="EVALUATING",
    )
    db_session.add(job)
    db_session.flush()

    sme_set = _create_published_sme_v1(db_session)
    snap = EvaluationFormSnapshot(
        snapshot_id=uuid.uuid4(),
        evaluation_id=job.evaluation_id,
        agent_id="sme",
        rubric_set_id=sme_set.rubric_set_id,
        snapshot_payload={"form": "data"},
        snapshot_hash="a" * 64,
        adapter_key="sme",
        adapter_version=1,
    )
    db_session.add(snap)
    db_session.commit()

    # Update attempt must fail
    with pytest.raises((IntegrityError, DatabaseError), match="immutable"):
        db_session.execute(
            update(EvaluationFormSnapshot)
            .where(EvaluationFormSnapshot.snapshot_id == snap.snapshot_id)
            .values(adapter_version=2)
        )
        db_session.commit()
    db_session.rollback()

    # Delete attempt must fail
    with pytest.raises((IntegrityError, DatabaseError), match="immutable"):
        db_session.execute(
            delete(EvaluationFormSnapshot).where(
                EvaluationFormSnapshot.snapshot_id == snap.snapshot_id
            )
        )
        db_session.commit()
    db_session.rollback()


# ---------------------------------------------------------------------------
# Repository Shared Locking & Lifecycle Primitives
# ---------------------------------------------------------------------------


def test_lock_draft_rubric_set_immutability(db_session):
    """Locking non-draft set raises ValueError to prevent mutating published sets."""
    sme_set = _create_published_sme_v1(db_session)
    with pytest.raises(ValueError, match="published/retired definitions are immutable"):
        lock_draft_rubric_set(db_session, sme_set.rubric_set_id)


def test_create_draft_from_active_and_edit_lifecycle(db_session, test_admin_user):
    """Admin creates draft cloned from active revision, edits it, and publishes it."""
    _create_published_sme_v1(db_session, actor_id=test_admin_user.user_id)

    draft = create_draft_from_active(
        db_session, "sme", actor_id=test_admin_user.user_id
    )
    assert draft.status == "draft"
    assert draft.version_number == 2
    assert draft.created_by == test_admin_user.user_id

    # Verify cloned children
    domains = (
        db_session.query(RubricDomain)
        .filter_by(rubric_set_id=draft.rubric_set_id)
        .all()
    )
    assert len(domains) == 1
    assert domains[0].code == "OP"

    # Cannot create second draft while first draft exists
    with pytest.raises(ValueError, match="A draft already exists"):
        create_draft_from_active(db_session, "sme", actor_id=test_admin_user.user_id)

    # Publish draft with activation
    published_v2, activation = publish_draft_revision(
        db_session,
        draft.rubric_set_id,
        actor_id=test_admin_user.user_id,
        activate=True,
    )
    assert published_v2.status == "published"
    assert published_v2.published_by == test_admin_user.user_id
    assert activation is not None
    assert activation.rubric_set_id == published_v2.rubric_set_id

    # Active pointer now returns v2
    active_form = get_active_form_definition(db_session, "sme")
    assert active_form.version_number == 2


def test_activate_and_retire_rules(db_session, test_admin_user):
    """Retirement cannot target active revision; activating allows retiring former."""
    sme_v1 = _create_published_sme_v1(db_session, actor_id=test_admin_user.user_id)

    # Cannot retire currently active revision
    with pytest.raises(ValueError, match="Cannot retire active revision"):
        retire_revision(
            db_session, "sme", sme_v1.rubric_set_id, actor_id=test_admin_user.user_id
        )

    # Create and publish v2
    draft_v2 = create_draft_from_active(
        db_session, "sme", actor_id=test_admin_user.user_id
    )
    _v2, _act = publish_draft_revision(
        db_session,
        draft_v2.rubric_set_id,
        actor_id=test_admin_user.user_id,
        activate=True,
    )

    # Now v1 is inactive published, so it CAN be retired
    retired_v1 = retire_revision(
        db_session, "sme", sme_v1.rubric_set_id, actor_id=test_admin_user.user_id
    )
    assert retired_v1.status == "retired"
    assert retired_v1.retired_by == test_admin_user.user_id

    # Cannot activate retired revision
    with pytest.raises(ValueError, match="must be 'published'"):
        activate_revision(
            db_session, "sme", sme_v1.rubric_set_id, actor_id=test_admin_user.user_id
        )


def test_delete_draft_revision(db_session, test_admin_user):
    """Deleting draft cleans up draft children without touching published sets."""
    sme_v1 = _create_published_sme_v1(db_session, actor_id=test_admin_user.user_id)
    draft = create_draft_from_active(
        db_session, "sme", actor_id=test_admin_user.user_id
    )

    delete_draft_revision(db_session, draft.rubric_set_id)

    # Draft is gone
    assert (
        db_session.query(RubricSet)
        .filter_by(rubric_set_id=draft.rubric_set_id)
        .one_or_none()
        is None
    )
    # Published v1 is untouched
    assert (
        db_session.query(RubricSet)
        .filter_by(rubric_set_id=sme_v1.rubric_set_id)
        .one_or_none()
        is not None
    )


def test_get_active_form_definition_fails_on_unknown_agent(db_session):
    """Loading active form definition for an unknown agent raises ValueError."""
    now = datetime.now(UTC)
    unknown_set = RubricSet(
        rubric_set_id=uuid.uuid4(),
        agent_id="unknown_agent",
        name="Unknown Agent Rubric",
        version_number=1,
        status="published",
        adapter_key="unknown_agent",
        adapter_version=1,
        published_at=now,
        created_at=now,
    )
    db_session.add(unknown_set)
    db_session.flush()

    domain = RubricDomain(
        rubric_domain_id=uuid.uuid4(),
        rubric_set_id=unknown_set.rubric_set_id,
        code="UK",
        title="Unknown Domain",
        display_order=1,
    )
    db_session.add(domain)
    db_session.flush()

    criterion = RubricCriterion(
        rubric_criterion_id=uuid.uuid4(),
        rubric_domain_id=domain.rubric_domain_id,
        criterion_code="UK-01",
        title="Unknown Criterion",
        description="Unknown Description",
        scoring_rule="Unknown Rule",
        scoring_strategy="llm_rubric_guidance",
        strategy_config={
            "strategy": "llm_rubric_guidance",
            "guidance": "Unknown Guidance",
        },
        display_order=1,
    )
    db_session.add(criterion)
    db_session.flush()

    activation = RubricAgentActivation(
        agent_id="unknown_agent",
        rubric_set_id=unknown_set.rubric_set_id,
        updated_by=None,
        updated_at=now,
    )
    db_session.add(activation)
    db_session.commit()

    with pytest.raises(ValueError, match="Unknown agent capability manifest"):
        get_active_form_definition(db_session, "unknown_agent")


def test_create_draft_from_active_rejects_non_published_or_invalid(
    db_session, test_admin_user
):
    """create_draft_from_active fails & inserts no draft if active source invalid."""
    sme_set = _create_published_sme_v1(db_session, actor_id=test_admin_user.user_id)

    # 1. Non-published status (e.g. retired)
    sme_set.status = "retired"
    db_session.flush()
    with pytest.raises(ValueError, match="must be 'published'"):
        create_draft_from_active(db_session, "sme", actor_id=test_admin_user.user_id)
    assert (
        db_session.query(RubricSet).filter_by(agent_id="sme", status="draft").count()
        == 0
    )

    # Reset to published
    sme_set.status = "published"
    db_session.flush()

    # 2. Corrupted criterion scoring_strategy != strategy_config
    crit = db_session.query(RubricCriterion).filter_by(criterion_code="OP-02").one()
    crit.scoring_strategy = "ratio_band"
    db_session.flush()
    with pytest.raises(ValueError, match="does not match strategy_config"):
        create_draft_from_active(db_session, "sme", actor_id=test_admin_user.user_id)
    assert (
        db_session.query(RubricSet).filter_by(agent_id="sme", status="draft").count()
        == 0
    )


def test_publish_draft_with_activate_missing_activation_leaves_draft_unchanged(
    db_session, test_admin_user
):
    """publish_draft_revision(activate=True) rejects missing pointer safely."""
    now = datetime.now(UTC)
    draft_set = RubricSet(
        rubric_set_id=uuid.uuid4(),
        agent_id="gad",
        name="GAD Rubric Draft",
        version_number=1,
        status="draft",
        adapter_key="gad",
        adapter_version=1,
        created_by=test_admin_user.user_id,
        created_at=now,
    )
    db_session.add(draft_set)
    db_session.flush()

    dom = RubricDomain(
        rubric_domain_id=uuid.uuid4(),
        rubric_set_id=draft_set.rubric_set_id,
        code="GAD",
        title="Gender & Development",
        display_order=1,
    )
    db_session.add(dom)
    db_session.flush()

    crit = RubricCriterion(
        rubric_criterion_id=uuid.uuid4(),
        rubric_domain_id=dom.rubric_domain_id,
        criterion_code="GAD-01",
        title="Gender Responsive Language",
        description="Check gender responsive language.",
        scoring_rule="Maximum count mode.",
        scoring_strategy="count_band",
        strategy_config={
            "strategy": "count_band",
            "mode": "maximum_count",
            "threshold_4": 0,
            "threshold_3": 1,
            "threshold_2": 3,
        },
        display_order=1,
    )
    db_session.add(crit)
    db_session.commit()

    # No activation pointer exists for "gad". Attempt publish with activate=True
    with pytest.raises(ValueError, match="no existing activation pointer found"):
        publish_draft_revision(
            db_session,
            draft_set.rubric_set_id,
            actor_id=test_admin_user.user_id,
            activate=True,
        )

    # Draft remains unmutated in draft status
    refreshed = (
        db_session.query(RubricSet)
        .filter_by(rubric_set_id=draft_set.rubric_set_id)
        .one()
    )
    assert refreshed.status == "draft"
    assert refreshed.published_at is None
    assert refreshed.published_by is None


def test_deployed_low_prompt_budget_rejects_lifecycle_operations(
    db_session, test_admin_user, monkeypatch
):
    """Low deployed prompt budget setting rejects active load, activation, etc."""
    from server.core.config import Settings

    sme_set = _create_published_sme_v1(db_session, actor_id=test_admin_user.user_id)

    # Patch settings to have a very low SME budget
    low_settings = Settings(sme_total_prompt_budget_chars=10)
    monkeypatch.setattr(
        "server.modules.rubrics.repository.get_settings", lambda: low_settings
    )

    # 1. get_active_form_definition fails
    with pytest.raises(ValueError, match="exceeds prompt budget 10"):
        get_active_form_definition(db_session, "sme")

    # 2. activate_revision fails
    with pytest.raises(ValueError, match="exceeds prompt budget 10"):
        activate_revision(
            db_session,
            "sme",
            sme_set.rubric_set_id,
            actor_id=test_admin_user.user_id,
        )

    # 3. create_draft_from_active fails before creating draft
    with pytest.raises(ValueError, match="exceeds prompt budget 10"):
        create_draft_from_active(db_session, "sme", actor_id=test_admin_user.user_id)
    assert (
        db_session.query(RubricSet).filter_by(agent_id="sme", status="draft").count()
        == 0
    )

    # Restore normal settings to create a valid draft
    monkeypatch.setattr(
        "server.modules.rubrics.repository.get_settings",
        lambda: Settings(sme_total_prompt_budget_chars=15000),
    )
    draft = create_draft_from_active(
        db_session, "sme", actor_id=test_admin_user.user_id
    )

    # Re-apply low budget
    monkeypatch.setattr(
        "server.modules.rubrics.repository.get_settings", lambda: low_settings
    )

    # 4. publish_draft_revision fails
    with pytest.raises(ValueError, match="exceeds prompt budget 10"):
        publish_draft_revision(
            db_session,
            draft.rubric_set_id,
            actor_id=test_admin_user.user_id,
            activate=True,
        )
    assert (
        db_session.query(RubricSet)
        .filter_by(rubric_set_id=draft.rubric_set_id)
        .one()
        .status
        == "draft"
    )
