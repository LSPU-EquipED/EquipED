"""Tests for the run-status record on training jobs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from server.modules.training_data.exceptions import TrainingJobNotFoundError
from server.modules.training_data.jobs import (
    create_training_job,
    mark_run_stage,
    report_run_status,
)
from server.modules.training_data.models import DpoTrainingJob
from server.modules.training_data.tokens import hash_token

from .conftest import seed_eligible_dpo_pair


@pytest.fixture
def created(db_session, admin_user):
    seed_eligible_dpo_pair(db_session, owner_id=admin_user.user_id, agent_id="gad")
    return create_training_job(db_session, "gad", admin_user.user_id)


def _job(db_session, created) -> DpoTrainingJob:
    db_session.expire_all()
    return db_session.get(DpoTrainingJob, created.job.job_id)


def test_new_jobs_get_a_status_token_that_expires_with_the_upload_token(
    db_session, created
):
    job = _job(db_session, created)
    assert job.status_token_hash == hash_token(created.raw_status_token)
    assert job.status_expires_at is not None
    assert job.run_stage is None


def test_report_stores_stage_step_total_and_time(db_session, created):
    report_run_status(
        db_session,
        created.job.job_id,
        created.raw_status_token,
        "training",
        step=14,
        total=30,
    )
    job = _job(db_session, created)
    assert (job.run_stage, job.run_step, job.run_total) == ("training", 14, 30)
    assert job.run_reported_at is not None


def test_message_is_truncated_to_500_characters(db_session, created):
    report_run_status(
        db_session,
        created.job.job_id,
        created.raw_status_token,
        "failed",
        message="x" * 900,
    )
    assert len(_job(db_session, created).run_message) == 500


@pytest.mark.parametrize("bad", ["wrong", ""])
def test_wrong_token_is_rejected_as_not_found(db_session, created, bad):
    with pytest.raises(TrainingJobNotFoundError):
        report_run_status(db_session, created.job.job_id, bad, "training")


def test_unknown_job_is_rejected_as_not_found(db_session, created):
    with pytest.raises(TrainingJobNotFoundError):
        report_run_status(
            db_session, uuid.uuid4(), created.raw_status_token, "training"
        )


def test_expired_token_is_rejected(db_session, created):
    job = _job(db_session, created)
    job.status_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()
    with pytest.raises(TrainingJobNotFoundError):
        report_run_status(
            db_session, created.job.job_id, created.raw_status_token, "training"
        )


def test_old_job_without_a_status_token_cannot_report(db_session, created):
    job = _job(db_session, created)
    job.status_token_hash = None
    job.status_expires_at = None
    db_session.commit()
    with pytest.raises(TrainingJobNotFoundError):
        report_run_status(
            db_session, created.job.job_id, created.raw_status_token, "training"
        )


def test_stage_never_moves_backwards(db_session, created):
    mark_run_stage(db_session, created.job.job_id, "converting")
    report_run_status(
        db_session, created.job.job_id, created.raw_status_token, "training", step=3
    )
    assert _job(db_session, created).run_stage == "converting"


def test_same_stage_repeats_update_the_counter(db_session, created):
    for step in (1, 2):
        report_run_status(
            db_session,
            created.job.job_id,
            created.raw_status_token,
            "training",
            step=step,
            total=10,
        )
    assert _job(db_session, created).run_step == 2


def test_failed_is_recorded_but_not_after_finished(db_session, created):
    report_run_status(
        db_session,
        created.job.job_id,
        created.raw_status_token,
        "failed",
        message="OOM",
    )
    assert _job(db_session, created).run_stage == "failed"
    mark_run_stage(db_session, created.job.job_id, "finished")
    assert _job(db_session, created).run_stage == "finished"
    report_run_status(
        db_session,
        created.job.job_id,
        created.raw_status_token,
        "failed",
        message="late",
    )
    assert _job(db_session, created).run_stage == "finished"


def test_a_run_can_restart_after_failing(db_session, created):
    report_run_status(
        db_session, created.job.job_id, created.raw_status_token, "failed"
    )
    report_run_status(
        db_session, created.job.job_id, created.raw_status_token, "training", step=1
    )
    assert _job(db_session, created).run_stage == "training"


def test_mark_run_stage_never_raises_for_an_unknown_job(db_session):
    mark_run_stage(db_session, uuid.uuid4(), "finished")  # must not raise
