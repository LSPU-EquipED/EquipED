from __future__ import annotations

import copy
import hashlib
import json
from uuid import uuid4

import pytest
from server.modules.feedback.models import PreferenceLog
from server.modules.synthesis.models import AgentGeneration
from server.modules.training_data.job_packages import (
    freeze_job_dataset,
    preview_dataset_manifest,
)
from server.modules.training_data.jobs import create_training_job
from server.modules.training_data.models import DpoTrainingJob
from server.tests.training_data.conftest import seed_eligible_dpo_pair as _seed
from sqlalchemy.exc import IntegrityError


def seed_eligible_dpo_pair(session, owner, agent):
    job = _seed(session, owner, agent)
    gen = (
        session.query(AgentGeneration).filter_by(evaluation_id=job.evaluation_id).one()
    )
    gen.prompt_sha256 = hashlib.sha256(gen.prompt_text.encode()).hexdigest()
    gen.response_sha256 = hashlib.sha256(gen.response_text.encode()).hexdigest()
    session.commit()
    return job


def test_active_source_readiness_and_new_jobs_ignore_later_feedback(
    db_session, admin_user
):
    evaluation = seed_eligible_dpo_pair(db_session, admin_user.user_id, "gad")
    source = create_training_job(db_session, "gad", admin_user.user_id).job
    source.is_active_training_source = True
    db_session.commit()
    before = (
        source.pairs_content,
        source.provenance_content,
        copy.deepcopy(source.manifest_json),
    )
    original = (
        db_session.query(AgentGeneration)
        .filter_by(evaluation_id=evaluation.evaluation_id)
        .one()
    )
    attrs = {
        c.name: getattr(original, c.name)
        for c in AgentGeneration.__table__.columns
        if c.name not in ("generation_id", "created_at")
    }
    attrs["unit_key"] = "another_envelope"
    db_session.add(AgentGeneration(generation_id=uuid4(), **attrs))
    db_session.add(
        PreferenceLog(
            evaluation_id=evaluation.evaluation_id,
            user_id=admin_user.user_id,
            agent_name="gad",
            criterion_id="GAD-01",
            action="EDIT",
            edited_json={"score": 4, "justification": "New feedback"},
        )
    )
    db_session.commit()

    assert preview_dataset_manifest(db_session, "gad").pair_count == 1
    frozen = freeze_job_dataset(db_session, "gad")
    assert frozen.pairs_content == before[0]
    new = create_training_job(db_session, "gad", admin_user.user_id).job
    assert (new.pairs_content, new.provenance_content, new.manifest_json) == before
    assert not new.is_active_training_source
    assert db_session.query(PreferenceLog).count() == 2

    source.is_active_training_source = False
    db_session.commit()
    assert preview_dataset_manifest(db_session, "gad").pair_count == 2
    assert (new.pairs_content, new.provenance_content, new.manifest_json) == before


def test_only_one_active_source_per_agent(db_session, admin_user):
    seed_eligible_dpo_pair(db_session, admin_user.user_id, "gad")
    a = create_training_job(db_session, "gad", admin_user.user_id).job
    b = create_training_job(db_session, "gad", admin_user.user_id).job
    a.is_active_training_source = True
    b.is_active_training_source = True
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_invalid_active_package_does_not_fall_back_to_old_feedback(
    db_session, admin_user
):
    seed_eligible_dpo_pair(db_session, admin_user.user_id, "gad")
    source = create_training_job(db_session, "gad", admin_user.user_id).job
    source.is_active_training_source = True
    source.pairs_content += "corruption"
    db_session.commit()
    with pytest.raises(ValueError, match="hash"):
        preview_dataset_manifest(db_session, "gad")
    count = db_session.query(DpoTrainingJob).count()
    with pytest.raises(ValueError, match="hash"):
        create_training_job(db_session, "gad", admin_user.user_id)
    assert db_session.query(DpoTrainingJob).count() == count


def test_import_and_activation_are_atomic_and_admin_only(
    db_session, admin_user, faculty_user
):
    from server.modules.training_data.sources import register_training_source

    seed_eligible_dpo_pair(db_session, admin_user.user_id, "gad")
    original = create_training_job(db_session, "gad", admin_user.user_id).job
    original.is_active_training_source = True
    db_session.commit()
    package = freeze_job_dataset(db_session, "gad")
    count = db_session.query(DpoTrainingJob).count()
    with pytest.raises(PermissionError):
        register_training_source(db_session, "gad", faculty_user.user_id, package)
    assert db_session.query(DpoTrainingJob).count() == count
    imported = register_training_source(db_session, "gad", admin_user.user_id, package)
    assert imported.job.is_active_training_source
    db_session.rollback()
    db_session.refresh(original)
    assert original.is_active_training_source
    assert db_session.query(DpoTrainingJob).count() == count


def test_inactive_admin_cannot_register_source(db_session, admin_user):
    from server.modules.training_data.sources import register_training_source

    seed_eligible_dpo_pair(db_session, admin_user.user_id, "gad")
    package = freeze_job_dataset(db_session, "gad")
    admin_user.is_active = False
    db_session.commit()
    with pytest.raises(PermissionError):
        register_training_source(db_session, "gad", admin_user.user_id, package)
    assert db_session.query(DpoTrainingJob).count() == 0


def test_validate_import_checks_provenance_not_only_hashes(db_session, admin_user):
    from server.modules.training_data.contracts import FrozenJobPackage
    from server.modules.training_data.sources import validate_training_package

    seed_eligible_dpo_pair(db_session, admin_user.user_id, "gad")
    package = freeze_job_dataset(db_session, "gad")
    manifest = copy.deepcopy(package.manifest_json)
    prov = json.loads(package.provenance_content)
    prov["prompt_sha256"] = "0" * 64
    content = json.dumps(prov) + "\n"
    manifest["provenance_sha256"] = hashlib.sha256(content.encode()).hexdigest()
    manifest["provenance_bytes"] = len(content.encode())
    with pytest.raises(ValueError, match="prompt hash"):
        validate_training_package(
            FrozenJobPackage(package.pairs_content, content, manifest), "gad"
        )


def test_import_accepts_manifest_contracts_of_skipped_legacy_generations(
    db_session, admin_user
):
    from server.modules.training_data.sources import validate_training_package

    evaluation = seed_eligible_dpo_pair(db_session, admin_user.user_id, "gad")
    original = (
        db_session.query(AgentGeneration)
        .filter_by(evaluation_id=evaluation.evaluation_id)
        .one()
    )
    attrs = {
        c.name: getattr(original, c.name)
        for c in AgentGeneration.__table__.columns
        if c.name not in ("generation_id", "created_at")
    }
    attrs.update(unit_key="legacy", response_contract_key="gad_extraction.v1")
    db_session.add(AgentGeneration(generation_id=uuid4(), **attrs))
    db_session.commit()

    package = freeze_job_dataset(db_session, "gad")
    assert package.manifest_json["pair_count"] == 1
    assert set(package.manifest_json["response_contract_keys"]) == {
        "gad_scores.v1",
        "gad_extraction.v1",
    }
    validate_training_package(package, "gad")
    from server.modules.training_data.contracts import FrozenJobPackage

    missing_contract = copy.deepcopy(package.manifest_json)
    missing_contract["response_contract_keys"] = ["gad_extraction.v1"]
    with pytest.raises(ValueError, match="manifest totals"):
        validate_training_package(
            FrozenJobPackage(
                package.pairs_content, package.provenance_content, missing_contract
            ),
            "gad",
        )


@pytest.mark.parametrize("field", ["pair_id", "created_at"])
def test_import_obeys_existing_notebook_provenance_contract(
    db_session, admin_user, field
):
    from server.modules.training_data.contracts import FrozenJobPackage
    from server.modules.training_data.sources import validate_training_package

    seed_eligible_dpo_pair(db_session, admin_user.user_id, "gad")
    package = freeze_job_dataset(db_session, "gad")
    manifest = copy.deepcopy(package.manifest_json)
    prov = json.loads(package.provenance_content)
    if field == "pair_id":
        prov[field] = str(uuid4())
    else:
        del prov[field]
    content = json.dumps(prov) + "\n"
    manifest["provenance_sha256"] = hashlib.sha256(content.encode()).hexdigest()
    manifest["provenance_bytes"] = len(content.encode())
    with pytest.raises(ValueError, match=field):
        validate_training_package(
            FrozenJobPackage(package.pairs_content, content, manifest), "gad"
        )


def test_admin_readiness_and_start_job_use_active_source(
    client, auth_cookies_admin, admin_user, db_session
):
    from server.tests.admin.conftest import _auth

    seed_eligible_dpo_pair(db_session, admin_user.user_id, "gad")
    source = create_training_job(db_session, "gad", admin_user.user_id).job
    source.is_active_training_source = True
    db_session.commit()
    _auth(client, auth_cookies_admin)
    readiness = client.get("/api/v1/admin/training-data/gad/readiness")
    assert readiness.status_code == 200
    assert readiness.json()["pairs_sha256"] == source.manifest_json["pairs_sha256"]
    response = client.post("/api/v1/admin/training-data/gad/jobs")
    assert response.status_code == 201
    import uuid

    new = db_session.get(DpoTrainingJob, uuid.UUID(response.json()["job_id"]))
    assert new.pairs_content == source.pairs_content
    assert new.manifest_json == source.manifest_json


def test_invalid_active_source_returns_clear_error_without_creating_job(
    client, auth_cookies_admin, admin_user, db_session
):
    from server.tests.admin.conftest import _auth

    seed_eligible_dpo_pair(db_session, admin_user.user_id, "gad")
    source = create_training_job(db_session, "gad", admin_user.user_id).job
    source.is_active_training_source = True
    source.pairs_content += "broken"
    db_session.commit()
    _auth(client, auth_cookies_admin)
    assert client.get("/api/v1/admin/training-data/gad/readiness").status_code == 422
    assert client.post("/api/v1/admin/training-data/gad/jobs").status_code == 422
    assert db_session.query(DpoTrainingJob).count() == 1
