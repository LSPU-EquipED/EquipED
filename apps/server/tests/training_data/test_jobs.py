from __future__ import annotations

import uuid
from datetime import UTC, datetime

from server.modules.training_data.models import DpoTrainingJob, TrainedAdapter


def test_dpo_training_job_round_trips(db_session, admin_user):
    job = DpoTrainingJob(
        job_id=uuid.uuid4(),
        agent_id="gad",
        status="pending",
        created_by=admin_user.user_id,
        pairs_content="",
        provenance_content="",
        manifest_json={},
        download_token_hash="a" * 64,
        download_expires_at=datetime.now(UTC),
        upload_token_hash="b" * 64,
        upload_expires_at=datetime.now(UTC),
    )
    db_session.add(job)
    db_session.commit()

    fetched = db_session.get(DpoTrainingJob, job.job_id)
    assert fetched is not None
    assert fetched.agent_id == "gad"
    assert fetched.status == "pending"


def test_trained_adapter_round_trips(db_session, admin_user):
    job = DpoTrainingJob(
        job_id=uuid.uuid4(),
        agent_id="gad",
        status="completed",
        created_by=admin_user.user_id,
        pairs_content="",
        provenance_content="",
        manifest_json={},
        download_token_hash="a" * 64,
        download_expires_at=datetime.now(UTC),
        upload_token_hash="b" * 64,
        upload_expires_at=datetime.now(UTC),
    )
    db_session.add(job)
    db_session.flush()

    adapter = TrainedAdapter(
        adapter_id=uuid.uuid4(),
        agent_id="gad",
        job_id=job.job_id,
        version=1,
        file_path="adapters/gad/x/adapter.zip",
        file_sha256="c" * 64,
        size_bytes=1024,
    )
    db_session.add(adapter)
    db_session.commit()

    fetched = db_session.get(TrainedAdapter, adapter.adapter_id)
    assert fetched is not None
    assert fetched.job_id == job.job_id
    assert fetched.version == 1
