from __future__ import annotations

import json

from server.modules.training_data.job_packages import freeze_job_dataset
from server.modules.training_data.jobs import create_training_job
from server.modules.training_data.models import DpoTrainingJob
from server.tests.training_data.test_active_training_source import (
    seed_eligible_dpo_pair,
)


def test_import_dry_run_apply_and_restore(db_session, admin_user, tmp_path):
    from server.scripts.import_training_source import change_source, load_package

    seed_eligible_dpo_pair(db_session, admin_user.user_id, "gad")
    original = create_training_job(db_session, "gad", admin_user.user_id).job
    package = freeze_job_dataset(db_session, "gad")
    (tmp_path / "pairs.jsonl").write_bytes(package.pairs_content.encode())
    (tmp_path / "provenance.jsonl").write_bytes(package.provenance_content.encode())
    (tmp_path / "manifest.json").write_text(json.dumps(package.manifest_json))
    loaded = load_package(tmp_path)
    assert loaded == package
    preview = change_source(db_session, "gad", admin_user.user_id, loaded, apply=False)
    assert preview["pair_count"] == 1
    assert db_session.query(DpoTrainingJob).count() == 1
    assert not original.is_active_training_source
    receipt = change_source(db_session, "gad", admin_user.user_id, loaded, apply=True)
    assert receipt["action"] == "activated"
    assert db_session.query(DpoTrainingJob).count() == 2
    again = change_source(db_session, "gad", admin_user.user_id, loaded, apply=True)
    assert again["action"] == "already_active"
    assert db_session.query(DpoTrainingJob).count() == 2
    change_source(db_session, "gad", admin_user.user_id, None, apply=True)
    assert (
        not db_session.query(DpoTrainingJob)
        .filter_by(is_active_training_source=True)
        .count()
    )
    assert original.pairs_content == package.pairs_content


def test_target_fingerprint_ignores_credentials_and_rejects_routing_override():
    import pytest
    from server.scripts.import_training_source import target_fingerprint

    a = target_fingerprint("postgresql://admin:secret@db.test/equiped?sslmode=require")
    b = target_fingerprint("postgresql://app:different@db.test:5432/equiped")
    assert a == b
    with pytest.raises(ValueError, match="routing"):
        target_fingerprint("postgresql://app:secret@db.test/equiped?host=other.test")


def test_valid_import_replaces_corrupt_source_atomically(db_session, admin_user):
    from server.scripts.import_training_source import change_source

    seed_eligible_dpo_pair(db_session, admin_user.user_id, "gad")
    original = create_training_job(db_session, "gad", admin_user.user_id).job
    package = freeze_job_dataset(db_session, "gad")
    original.is_active_training_source = True
    original.pairs_content += "corrupt"
    db_session.commit()
    receipt = change_source(db_session, "gad", admin_user.user_id, package, apply=True)
    assert receipt["action"] == "activated"
    assert freeze_job_dataset(db_session, "gad") == package
    db_session.refresh(original)
    assert not original.is_active_training_source
    assert original.pairs_content.endswith("corrupt")
