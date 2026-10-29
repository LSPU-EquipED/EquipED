"""Coordinator v4 cutover preserves history and fails closed on unsafe state."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from equiped_harness.agents.coordinator.rubric import guidance_for
from server.modules.documents.models import Document
from server.modules.evaluations.models import EvaluationJob
from server.modules.rubrics.models import (
    EvaluationFormSnapshot,
    EvaluationRubricProvenance,
    RubricAgentActivation,
    RubricCriterion,
    RubricDomain,
    RubricSet,
)
from server.modules.rubrics.repository import activate_revision, publish_draft_revision
from server.modules.rubrics.service import upgrade_coordinator_harness
from server.scripts.seed_rubrics import seed_rubric_set
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[2]
RUBRIC_JSON = ROOT / "data" / "rubrics" / "rubrics.json"
_CODES = (
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
)


def _seed_active_v3(session) -> RubricSet:
    payload = json.loads(RUBRIC_JSON.read_text(encoding="utf-8"))
    source = copy.deepcopy(
        next(x for x in payload["rubric_sets"] if x["agent_id"] == "coordinator")
    )
    source.update(name="Coordinator active v3", version_number=1, status="active")
    for domain in source["domains"]:
        for criterion in domain["criteria"]:
            criterion.pop("scoring_strategy", None)
            criterion.pop("strategy_config", None)
    active = seed_rubric_set(session, source)
    active.status = "published"
    active.adapter_version = 3
    session.add(
        RubricAgentActivation(
            agent_id="coordinator", rubric_set_id=active.rubric_set_id
        )
    )
    session.flush()
    return active


def _shape(session, rubric_set_id):
    domains = list(
        session.scalars(
            select(RubricDomain)
            .where(RubricDomain.rubric_set_id == rubric_set_id)
            .order_by(RubricDomain.display_order)
        )
    )
    rows = []
    for domain in domains:
        rows.extend(
            session.scalars(
                select(RubricCriterion)
                .where(RubricCriterion.rubric_domain_id == domain.rubric_domain_id)
                .order_by(RubricCriterion.display_order)
            )
        )
    return (
        [(d.code, d.title, d.display_order) for d in domains],
        [
            (
                c.criterion_code,
                c.title,
                c.description,
                c.display_order,
                c.scoring_rule,
                c.scoring_strategy,
                c.strategy_config,
            )
            for c in rows
        ],
    )


def test_upgrade_preserves_old_rows_snapshots_and_is_idempotent(db_session, admin_user):
    active = _seed_active_v3(db_session)
    old_shape = _shape(db_session, active.rubric_set_id)
    document = Document(
        document_id=uuid4(),
        title="Historical SLM",
        source_type="slm",
        file_path="local/historical.pdf",
        uploaded_by=admin_user.user_id,
    )
    db_session.add(document)
    evaluation_id = uuid4()
    db_session.add(
        EvaluationJob(
            evaluation_id=evaluation_id,
            document_id=document.document_id,
            submitted_by=admin_user.user_id,
            status="COMPLETED",
            target_agent="coordinator",
            confirmed_program="BSCS",
            submitted_at=datetime.now(UTC),
        )
    )
    db_session.add(
        EvaluationRubricProvenance(
            rubric_set_id=active.rubric_set_id,
            agent_id="coordinator",
            version_number=active.version_number,
            name=active.name,
            adapter_key="coordinator",
            adapter_version=3,
        )
    )
    snapshot = EvaluationFormSnapshot(
        evaluation_id=evaluation_id,
        agent_id="coordinator",
        rubric_set_id=active.rubric_set_id,
        snapshot_payload={"frozen": "v3"},
        snapshot_hash="b" * 64,
        adapter_key="coordinator",
        adapter_version=3,
    )
    db_session.add(snapshot)
    db_session.commit()
    snapshot_identity = (
        snapshot.snapshot_id,
        snapshot.rubric_set_id,
        snapshot.snapshot_payload.copy(),
        snapshot.snapshot_hash,
        snapshot.adapter_version,
    )

    result = upgrade_coordinator_harness(db_session, actor_id=admin_user.user_id)
    assert (result.version_number, result.already_active) == (2, False)
    db_session.expire_all()
    old = db_session.get(RubricSet, active.rubric_set_id)
    new = db_session.get(RubricSet, result.rubric_set_id)
    activation = db_session.get(RubricAgentActivation, "coordinator")
    assert old.status == "published" and old.adapter_version == 3
    assert _shape(db_session, old.rubric_set_id) == old_shape
    assert activation.rubric_set_id == new.rubric_set_id
    assert new.status == "published" and new.adapter_version == 4
    assert new.created_by == new.published_by == admin_user.user_id
    assert _shape(db_session, new.rubric_set_id)[0] == old_shape[0]
    rows = _shape(db_session, new.rubric_set_id)[1]
    assert [row[:4] for row in rows] == [row[:4] for row in old_shape[1]]
    assert [row[0] for row in rows] == list(_CODES)
    for code, *_, strategy, raw_config in rows:
        expected = guidance_for(code).model_dump(mode="json")
        assert strategy == "llm_rubric_guidance"
        assert raw_config == expected
        assert [item["score"] for item in raw_config["level_descriptors"]] == [
            4,
            3,
            2,
            1,
        ]
    frozen = db_session.get(EvaluationFormSnapshot, snapshot_identity[0])
    assert (
        frozen.snapshot_id,
        frozen.rubric_set_id,
        frozen.snapshot_payload,
        frozen.snapshot_hash,
        frozen.adapter_version,
    ) == snapshot_identity
    assert db_session.get(EvaluationRubricProvenance, active.rubric_set_id) is not None
    repeated = upgrade_coordinator_harness(db_session, actor_id=admin_user.user_id)
    assert repeated == type(result)(new.rubric_set_id, 2, True)
    assert (
        len(
            list(
                db_session.scalars(
                    select(RubricSet).where(RubricSet.agent_id == "coordinator")
                )
            )
        )
        == 2
    )


def test_upgrade_preserves_existing_draft_and_publishes_new_revision(
    db_session, admin_user
):
    _seed_active_v3(db_session)
    draft = RubricSet(
        agent_id="coordinator",
        name="Existing draft",
        version_number=9,
        status="draft",
        adapter_key="coordinator",
        adapter_version=3,
        created_by=admin_user.user_id,
    )
    db_session.add(draft)
    db_session.flush()
    domain = RubricDomain(
        rubric_set_id=draft.rubric_set_id,
        code="DRAFT-DOMAIN",
        title="Draft title",
        display_order=7,
    )
    db_session.add(domain)
    db_session.flush()
    criterion = RubricCriterion(
        rubric_domain_id=domain.rubric_domain_id,
        criterion_code="DRAFT-01",
        title="Draft criterion",
        description="Draft content",
        scoring_rule="Draft scoring",
        scoring_strategy="manual",
        strategy_config={"draft": [1, 2]},
        display_order=3,
    )
    db_session.add(criterion)
    db_session.commit()
    draft_before = (
        draft.rubric_set_id,
        draft.agent_id,
        draft.name,
        draft.version_number,
        draft.status,
        draft.adapter_key,
        draft.adapter_version,
        draft.published_at,
        draft.published_by,
        draft.created_by,
        draft.created_at,
        _shape(db_session, draft.rubric_set_id),
    )
    result = upgrade_coordinator_harness(db_session, actor_id=admin_user.user_id)
    db_session.expire_all()
    preserved_draft = db_session.get(RubricSet, draft.rubric_set_id)
    assert (
        preserved_draft.rubric_set_id,
        preserved_draft.agent_id,
        preserved_draft.name,
        preserved_draft.version_number,
        preserved_draft.status,
        preserved_draft.adapter_key,
        preserved_draft.adapter_version,
        preserved_draft.published_at,
        preserved_draft.published_by,
        preserved_draft.created_by,
        preserved_draft.created_at,
        _shape(db_session, preserved_draft.rubric_set_id),
    ) == draft_before
    assert (
        db_session.get(RubricAgentActivation, "coordinator").rubric_set_id
        == result.rubric_set_id
    )
    new = db_session.get(RubricSet, result.rubric_set_id)
    assert new.status == "published" and new.adapter_version == 4
    assert new.version_number == 10
    assert new.published_at is not None
    assert (
        len(
            list(
                db_session.scalars(
                    select(RubricSet).where(RubricSet.agent_id == "coordinator")
                )
            )
        )
        == 3
    )


@pytest.mark.parametrize("target_agent", ["coordinator", "all"])
@pytest.mark.parametrize(
    "status", ["SUBMITTED", "PREPROCESSING", "EVALUATING", "SYNTHESIZING"]
)
def test_upgrade_waits_for_coordinator_jobs(
    db_session, admin_user, target_agent, status
):
    active = _seed_active_v3(db_session)
    document = Document(
        document_id=uuid4(),
        title="Queued SLM",
        source_type="slm",
        file_path="local/queued.pdf",
        uploaded_by=admin_user.user_id,
    )
    job = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=document.document_id,
        submitted_by=admin_user.user_id,
        status=status,
        target_agent=target_agent,
        submitted_at=datetime.now(UTC),
    )
    db_session.add_all([document, job])
    db_session.commit()
    with pytest.raises(RuntimeError, match="in-flight job"):
        upgrade_coordinator_harness(db_session, actor_id=admin_user.user_id)
    db_session.expire_all()
    assert (
        db_session.get(RubricAgentActivation, "coordinator").rubric_set_id
        == active.rubric_set_id
    )
    assert db_session.get(EvaluationJob, job.evaluation_id).status == status
    assert (
        len(
            list(
                db_session.scalars(
                    select(RubricSet).where(RubricSet.agent_id == "coordinator")
                )
            )
        )
        == 1
    )


def test_upgrade_requires_approved_admin_and_rolls_back_creation(
    db_session, admin_user, faculty_user, monkeypatch
):
    active = _seed_active_v3(db_session)
    db_session.commit()
    with pytest.raises(PermissionError, match="active approved administrator"):
        upgrade_coordinator_harness(db_session, actor_id=faculty_user.user_id)
    db_session.expire_all()
    assert (
        len(
            list(
                db_session.scalars(
                    select(RubricSet).where(RubricSet.agent_id == "coordinator")
                )
            )
        )
        == 1
    )
    import server.modules.rubrics.coordinator_upgrade as upgrade_module

    def fail_validation(_form):
        raise RuntimeError("forced validation failure")

    monkeypatch.setattr(upgrade_module, "validate_form_definition", fail_validation)
    with pytest.raises(RuntimeError, match="forced validation failure"):
        upgrade_coordinator_harness(db_session, actor_id=admin_user.user_id)
    db_session.expire_all()
    assert (
        db_session.get(RubricAgentActivation, "coordinator").rubric_set_id
        == active.rubric_set_id
    )
    assert (
        len(
            list(
                db_session.scalars(
                    select(RubricSet).where(RubricSet.agent_id == "coordinator")
                )
            )
        )
        == 1
    )


def test_retired_coordinator_adapter_cannot_be_reactivated_or_published(
    db_session, admin_user
):
    old = _seed_active_v3(db_session)
    db_session.commit()
    upgraded = upgrade_coordinator_harness(db_session, actor_id=admin_user.user_id)
    activation = db_session.get(RubricAgentActivation, "coordinator")
    assert activation.rubric_set_id == upgraded.rubric_set_id

    with pytest.raises(ValueError, match="adapter version 4 is required"):
        activate_revision(
            db_session,
            "coordinator",
            old.rubric_set_id,
            actor_id=admin_user.user_id,
        )
    db_session.refresh(activation)
    assert activation.rubric_set_id == upgraded.rubric_set_id
    assert old.status == "published"

    draft = RubricSet(
        agent_id="coordinator",
        name="Historical v3 draft",
        version_number=10,
        status="draft",
        adapter_key="coordinator",
        adapter_version=3,
        created_by=admin_user.user_id,
    )
    db_session.add(draft)
    db_session.flush()
    with pytest.raises(ValueError, match="adapter version 4 is required"):
        publish_draft_revision(
            db_session,
            draft.rubric_set_id,
            actor_id=admin_user.user_id,
            activate=True,
        )
    db_session.refresh(draft)
    db_session.refresh(activation)
    assert draft.status == "draft"
    assert activation.rubric_set_id == upgraded.rubric_set_id

    activate_revision(
        db_session,
        "coordinator",
        upgraded.rubric_set_id,
        actor_id=admin_user.user_id,
    )
    db_session.refresh(activation)
    assert activation.rubric_set_id == upgraded.rubric_set_id
