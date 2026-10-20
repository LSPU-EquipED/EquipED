"""Explicit ITSO v3 cutover preserves history and chooses guidance coherently."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
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
from server.modules.rubrics.service import upgrade_itso_harness
from server.scripts.seed_rubrics import seed_rubric_set
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[2]
RUBRIC_JSON = ROOT / "data" / "rubrics" / "rubrics.json"


def _seed_legacy_itso(session) -> RubricSet:
    payload = json.loads(RUBRIC_JSON.read_text(encoding="utf-8"))
    itso = copy.deepcopy(
        next(x for x in payload["rubric_sets"] if x["agent_id"] == "itso")
    )
    itso.update(name="ITSO Rubric v1", version_number=1, adapter_version=1)
    for domain in itso["domains"]:
        for criterion in domain["criteria"]:
            criterion.pop("scoring_strategy", None)
            criterion.pop("strategy_config", None)
    itso["status"] = "active"
    return seed_rubric_set(session, itso)


def _guidance_rubric(*, version: int, status: str, prefix: str) -> dict:
    payload = json.loads(RUBRIC_JSON.read_text(encoding="utf-8"))
    itso = copy.deepcopy(
        next(x for x in payload["rubric_sets"] if x["agent_id"] == "itso")
    )
    itso.update(
        name=f"ITSO v1 guidance {version}",
        version_number=version,
        status=status,
        adapter_version=1,
    )
    for domain in itso["domains"]:
        for criterion in domain["criteria"]:
            code = criterion["criterion_code"]
            criterion["scoring_strategy"] = "llm_rubric_guidance"
            criterion["strategy_config"] = {
                "strategy": "llm_rubric_guidance",
                "guidance": f"{prefix}: {code}",
                "level_descriptors": None,
            }
    return itso


def _source_shape(session, rubric_set_id):
    domains = list(
        session.scalars(
            select(RubricDomain).where(RubricDomain.rubric_set_id == rubric_set_id)
        )
    )
    criteria = []
    for domain in domains:
        criteria.extend(
            session.scalars(
                select(RubricCriterion).where(
                    RubricCriterion.rubric_domain_id == domain.rubric_domain_id
                )
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
                c.scoring_strategy,
                c.strategy_config,
            )
            for c in criteria
        ],
    )


def test_upgrade_preserves_legacy_rows_and_is_idempotent(db_session, admin_user):
    legacy = _seed_legacy_itso(db_session)
    for criterion in db_session.scalars(
        select(RubricCriterion)
        .join(RubricDomain)
        .where(RubricDomain.rubric_set_id == legacy.rubric_set_id)
    ):
        criterion.scoring_strategy = "llm_rubric_guidance"
        criterion.strategy_config = {
            "strategy": "llm_rubric_guidance",
            "guidance": f"active v1 guidance: {criterion.criterion_code}",
            "level_descriptors": None,
        }
    db_session.flush()
    legacy_shape = _source_shape(db_session, legacy.rubric_set_id)
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
            target_agent="itso",
            confirmed_program="BSCS",
            submitted_at=datetime.now(UTC),
        )
    )
    db_session.add(
        EvaluationRubricProvenance(
            rubric_set_id=legacy.rubric_set_id,
            agent_id="itso",
            version_number=legacy.version_number,
            name=legacy.name,
            adapter_key="itso",
            adapter_version=1,
        )
    )
    old_snapshot = EvaluationFormSnapshot(
        evaluation_id=evaluation_id,
        agent_id="itso",
        rubric_set_id=legacy.rubric_set_id,
        snapshot_payload={"historical": "legacy"},
        snapshot_hash="a" * 64,
        adapter_key="itso",
        adapter_version=1,
    )
    db_session.add(old_snapshot)
    db_session.commit()
    snapshot_identity = (
        old_snapshot.snapshot_id,
        old_snapshot.rubric_set_id,
        old_snapshot.snapshot_payload.copy(),
        old_snapshot.snapshot_hash,
        old_snapshot.adapter_version,
    )

    result = upgrade_itso_harness(db_session, actor_id=admin_user.user_id)
    assert result.version_number == 2
    assert not result.already_active
    db_session.expire_all()

    old = db_session.get(RubricSet, legacy.rubric_set_id)
    activation = db_session.get(RubricAgentActivation, "itso")
    new = db_session.get(RubricSet, result.rubric_set_id)
    assert old.status == "published" and old.adapter_version == 1
    assert _source_shape(db_session, old.rubric_set_id) == legacy_shape
    snapshot = db_session.get(EvaluationFormSnapshot, snapshot_identity[0])
    assert (
        snapshot.snapshot_id,
        snapshot.rubric_set_id,
        snapshot.snapshot_payload,
        snapshot.snapshot_hash,
        snapshot.adapter_version,
    ) == snapshot_identity
    assert activation.rubric_set_id == new.rubric_set_id
    assert activation.updated_by == admin_user.user_id
    assert new.status == "published" and new.adapter_version == 3
    assert (
        new.published_by == admin_user.user_id and new.created_by == admin_user.user_id
    )
    _, upgraded_criteria = _source_shape(db_session, new.rubric_set_id)
    assert [row[:4] for row in upgraded_criteria] == [
        row[:4] for row in legacy_shape[1]
    ]
    assert all(row[4] == "llm_rubric_guidance" for row in upgraded_criteria)
    assert all(row[5]["strategy"] == "llm_rubric_guidance" for row in upgraded_criteria)
    assert [row[5]["guidance"] for row in upgraded_criteria] == [
        f"active v1 guidance: {row[0]}" for row in legacy_shape[1]
    ]

    repeated = upgrade_itso_harness(db_session, actor_id=admin_user.user_id)
    assert repeated == type(result)(new.rubric_set_id, 2, True)
    assert (
        len(
            list(
                db_session.scalars(
                    select(RubricSet).where(RubricSet.agent_id == "itso")
                )
            )
        )
        == 2
    )


def test_upgrade_uses_one_latest_v1_guidance_revision_for_active_v2(
    db_session, admin_user
):
    active = _seed_legacy_itso(db_session)
    for criterion in db_session.scalars(
        select(RubricCriterion)
        .join(RubricDomain)
        .where(RubricDomain.rubric_set_id == active.rubric_set_id)
    ):
        criterion.scoring_strategy = "llm_rubric_guidance"
        criterion.strategy_config = {
            "strategy": "llm_rubric_guidance",
            "guidance": f"older v1 guidance: {criterion.criterion_code}",
            "level_descriptors": None,
        }
    older_shape = _source_shape(db_session, active.rubric_set_id)

    latest_v1 = seed_rubric_set(
        db_session,
        _guidance_rubric(version=2, status="retired", prefix="latest v1 guidance"),
    )
    active.adapter_version = 2
    active.version_number = 3
    active.name = "Current evidence form"
    active.status = "published"
    for criterion in db_session.scalars(
        select(RubricCriterion)
        .join(RubricDomain)
        .where(RubricDomain.rubric_set_id == active.rubric_set_id)
    ):
        criterion.description = (
            f"Revised active description: {criterion.criterion_code}"
        )
    db_session.commit()

    result = upgrade_itso_harness(db_session, actor_id=admin_user.user_id)
    _, upgraded = _source_shape(db_session, result.rubric_set_id)
    _, current = _source_shape(db_session, active.rubric_set_id)
    assert [row[2] for row in upgraded] == [row[2] for row in current]
    assert [row[5]["guidance"] for row in upgraded] == [
        f"latest v1 guidance: {code}"
        for code in ("ITSO-01", "ITSO-02", "ITSO-03", "ITSO-04", "ITSO-05")
    ]
    assert latest_v1.status == "retired"
    assert [row[5]["guidance"] for row in older_shape[1]] == [
        f"older v1 guidance: {row[0]}" for row in older_shape[1]
    ]


def test_upgrade_rejects_noncanonical_criteria_without_writes(db_session, admin_user):
    legacy = _seed_legacy_itso(db_session)
    criterion = db_session.scalar(
        select(RubricCriterion).where(RubricCriterion.criterion_code == "ITSO-05")
    )
    criterion.criterion_code = "ITSO-X"
    db_session.commit()

    with pytest.raises(RuntimeError, match="exactly five canonical criteria"):
        upgrade_itso_harness(db_session, actor_id=admin_user.user_id)
    db_session.expire_all()
    assert (
        db_session.get(RubricAgentActivation, "itso").rubric_set_id
        == legacy.rubric_set_id
    )
    assert (
        len(
            list(
                db_session.scalars(
                    select(RubricSet).where(RubricSet.agent_id == "itso")
                )
            )
        )
        == 1
    )


def test_upgrade_stops_without_touching_existing_draft(db_session, admin_user):
    legacy = _seed_legacy_itso(db_session)
    draft = RubricSet(
        agent_id="itso",
        name="Existing draft",
        version_number=7,
        status="draft",
        adapter_key="itso",
        adapter_version=1,
        created_by=admin_user.user_id,
    )
    db_session.add(draft)
    db_session.commit()

    with pytest.raises(RuntimeError, match="existing ITSO draft must be resolved"):
        upgrade_itso_harness(db_session, actor_id=admin_user.user_id)
    db_session.expire_all()
    assert (
        db_session.get(RubricAgentActivation, "itso").rubric_set_id
        == legacy.rubric_set_id
    )
    assert db_session.get(RubricSet, draft.rubric_set_id).status == "draft"
    assert (
        len(
            list(
                db_session.scalars(
                    select(RubricSet).where(RubricSet.agent_id == "itso")
                )
            )
        )
        == 2
    )


def test_upgrade_requires_active_approved_admin(db_session, faculty_user):
    legacy = _seed_legacy_itso(db_session)
    db_session.commit()

    with pytest.raises(PermissionError, match="active approved administrator"):
        upgrade_itso_harness(db_session, actor_id=faculty_user.user_id)
    db_session.expire_all()
    assert (
        db_session.get(RubricAgentActivation, "itso").rubric_set_id
        == legacy.rubric_set_id
    )
    assert (
        len(
            list(
                db_session.scalars(
                    select(RubricSet).where(RubricSet.agent_id == "itso")
                )
            )
        )
        == 1
    )


def test_upgrade_does_not_require_legacy_workflow_tables(db_session, admin_user):
    legacy = _seed_legacy_itso(db_session)
    db_session.commit()
    connection = db_session.connection()
    connection.exec_driver_sql("DROP TABLE itso_assessments")

    result = upgrade_itso_harness(db_session, actor_id=admin_user.user_id)
    db_session.expire_all()
    assert (
        db_session.get(RubricAgentActivation, "itso").rubric_set_id
        == result.rubric_set_id
    )
    assert result.rubric_set_id != legacy.rubric_set_id
    assert (
        len(
            list(
                db_session.scalars(
                    select(RubricSet).where(RubricSet.agent_id == "itso")
                )
            )
        )
        == 2
    )


@pytest.mark.parametrize("target_agent", ["itso", "all"])
@pytest.mark.parametrize(
    "status", ["SUBMITTED", "PREPROCESSING", "EVALUATING", "SYNTHESIZING"]
)
def test_upgrade_waits_for_legacy_itso_jobs_to_drain(
    db_session, admin_user, target_agent, status
):
    legacy = _seed_legacy_itso(db_session)
    document = Document(
        document_id=uuid4(),
        title="Queued legacy SLM",
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

    with pytest.raises(RuntimeError, match="ITSO evaluation jobs are still in flight"):
        upgrade_itso_harness(db_session, actor_id=admin_user.user_id)
    db_session.expire_all()
    assert (
        db_session.get(RubricAgentActivation, "itso").rubric_set_id
        == legacy.rubric_set_id
    )
    assert db_session.get(EvaluationJob, job.evaluation_id).status == status
    assert (
        len(
            list(
                db_session.scalars(
                    select(RubricSet).where(RubricSet.agent_id == "itso")
                )
            )
        )
        == 1
    )
