from __future__ import annotations

import io
import uuid
import uuid as uuid_module
import zipfile
from datetime import UTC, datetime, timedelta

import pytest
from server.modules.evaluations.models import EvaluationJob
from server.modules.synthesis.models import AgentGeneration, AgentResult
from server.modules.training_data.exceptions import (
    InvalidAgentIdError,
    TrainingJobNotFoundError,
)
from server.modules.training_data.jobs import (
    create_training_job,
    get_job_download_package,
    list_training_jobs,
)
from server.modules.training_data.models import DpoTrainingJob, TrainedAdapter
from server.modules.training_data.tokens import hash_token
from server.tests.evaluations.conftest import _add_document


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


def _make_gad_generation(db_session, owner_id, agent_id="gad"):
    """Seed one evaluation with an AgentResult + AgentGeneration for
    agent_id. AgentGeneration.agent_result_id is NOT nullable (see
    server/modules/synthesis/models.py) -- an AgentResult row must exist
    first and its agent_result_id passed through, or this raises an
    IntegrityError."""
    document_id = _add_document(db_session, owner_id=owner_id, source_type="slm")
    job = EvaluationJob(evaluation_id=uuid_module.uuid4(), document_id=document_id)
    db_session.add(job)
    db_session.flush()

    agent_result = AgentResult(
        evaluation_id=job.evaluation_id,
        document_id=document_id,
        agent_name=agent_id,
        subtotal=2.0,
        processing_seconds=1.0,
        token_count=10,
        model_name="test-model",
        summary="GAD evaluation summary",
        success=True,
    )
    db_session.add(agent_result)
    db_session.flush()

    generation = AgentGeneration(
        generation_id=uuid_module.uuid4(),
        agent_result_id=agent_result.agent_result_id,
        evaluation_id=job.evaluation_id,
        document_id=document_id,
        agent_id=agent_id,
        unit_key="gad-01",
        criterion_ids=["GAD-01"],
        prompt_text="prompt",
        response_text='{"gad-01": {"score": 2, "reasoning": "r"}}',
        response_json={"gad-01": {"score": 2, "reasoning": "r"}},
        response_contract_key="gad_scores.v1",
        response_contract_version=1,
        model_name="test-model",
        envelope_status="ok",
        prompt_sha256="p" * 64,
        response_sha256="r" * 64,
    )
    db_session.add(generation)
    db_session.commit()
    return job.evaluation_id


def test_create_training_job_rejects_unknown_agent(db_session, admin_user):
    with pytest.raises(InvalidAgentIdError):
        create_training_job(db_session, "not-a-real-agent", admin_user.user_id)


def test_create_training_job_freezes_dataset_and_mints_tokens(db_session, admin_user):
    _make_gad_generation(db_session, owner_id=admin_user.user_id)

    result = create_training_job(db_session, "gad", admin_user.user_id)

    assert result.job.agent_id == "gad"
    assert result.job.status == "pending"
    assert result.job.created_by == admin_user.user_id
    assert isinstance(result.job.manifest_json, dict)
    assert result.job.download_token_hash == hash_token(result.raw_download_token)
    assert result.job.upload_token_hash == hash_token(result.raw_upload_token)
    assert result.raw_download_token != result.raw_upload_token

    fetched = db_session.get(DpoTrainingJob, result.job.job_id)
    assert fetched is not None
    assert fetched.status == "pending"


def test_get_job_download_package_returns_zip_with_expected_files(
    db_session, admin_user
):
    _make_gad_generation(db_session, owner_id=admin_user.user_id)
    result = create_training_job(db_session, "gad", admin_user.user_id)

    zip_bytes = get_job_download_package(
        db_session, result.job.job_id, result.raw_download_token
    )
    assert isinstance(zip_bytes, bytes)
    assert len(zip_bytes) > 0

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = set(zf.namelist())
        assert names == {"pairs.jsonl", "provenance.jsonl", "manifest.json"}

    refreshed = db_session.get(DpoTrainingJob, result.job.job_id)
    assert refreshed.status == "downloaded"
    assert refreshed.download_used_at is not None


def test_get_job_download_package_rejects_reuse(db_session, admin_user):
    _make_gad_generation(db_session, owner_id=admin_user.user_id)
    result = create_training_job(db_session, "gad", admin_user.user_id)

    get_job_download_package(db_session, result.job.job_id, result.raw_download_token)

    with pytest.raises(TrainingJobNotFoundError):
        get_job_download_package(
            db_session, result.job.job_id, result.raw_download_token
        )


def test_get_job_download_package_rejects_wrong_token(db_session, admin_user):
    _make_gad_generation(db_session, owner_id=admin_user.user_id)
    result = create_training_job(db_session, "gad", admin_user.user_id)

    with pytest.raises(TrainingJobNotFoundError):
        get_job_download_package(db_session, result.job.job_id, "wrong-token")


def test_get_job_download_package_rejects_unknown_job(db_session, admin_user):
    with pytest.raises(TrainingJobNotFoundError):
        get_job_download_package(db_session, uuid_module.uuid4(), "wrong-token")


def test_get_job_download_package_rejects_expired_token(db_session, admin_user):
    _make_gad_generation(db_session, owner_id=admin_user.user_id)
    result = create_training_job(db_session, "gad", admin_user.user_id)

    job = db_session.get(DpoTrainingJob, result.job.job_id)
    job.download_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()

    with pytest.raises(TrainingJobNotFoundError):
        get_job_download_package(
            db_session, result.job.job_id, result.raw_download_token
        )


def test_list_training_jobs_returns_newest_first(db_session, admin_user):
    _make_gad_generation(db_session, owner_id=admin_user.user_id)
    first = create_training_job(db_session, "gad", admin_user.user_id)
    second = create_training_job(db_session, "gad", admin_user.user_id)

    # server_default=func.now() resolves to SQLite's CURRENT_TIMESTAMP,
    # which has 1-second resolution -- two jobs created milliseconds apart
    # in-test can land on an identical created_at. Force a deterministic
    # ordering the same way test_get_job_download_package_rejects_expired_token
    # writes timestamps directly, rather than relying on wall-clock separation.
    first.job.created_at = datetime.now(UTC) - timedelta(seconds=1)
    second.job.created_at = datetime.now(UTC)
    db_session.commit()

    jobs = list_training_jobs(db_session, "gad")

    assert [j.job_id for j in jobs] == [second.job.job_id, first.job.job_id]


def test_list_training_jobs_filters_by_agent(db_session, admin_user):
    _make_gad_generation(db_session, owner_id=admin_user.user_id)
    create_training_job(db_session, "gad", admin_user.user_id)

    itso_jobs = list_training_jobs(db_session, "itso")
    assert itso_jobs == []
