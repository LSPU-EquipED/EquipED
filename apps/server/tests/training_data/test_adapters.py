"""apps/server/tests/training_data/test_adapters.py"""

from __future__ import annotations

import uuid as uuid_module

import pytest
from server.modules.evaluations.models import EvaluationJob
from server.modules.synthesis.models import AgentGeneration, AgentResult
from server.modules.training_data.adapters import (
    list_trained_adapters,
    store_adapter_upload,
)
from server.modules.training_data.exceptions import (
    AdapterUploadError,
    TrainingJobNotFoundError,
)
from server.modules.training_data.jobs import create_training_job
from server.modules.training_data.models import DpoTrainingJob
from server.tests.evaluations.conftest import _add_document


def _make_gad_generation(db_session, owner_id, agent_id="gad"):
    """See the identical helper's docstring in test_jobs.py (Task 4) for
    why AgentResult must be created first."""
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


def test_store_adapter_upload_writes_file_and_row(
    db_session, admin_user, tmp_path, monkeypatch
):
    monkeypatch.setattr("server.modules.training_data.adapters.ADAPTER_ROOT", tmp_path)
    _make_gad_generation(db_session, owner_id=admin_user.user_id)
    result = create_training_job(db_session, "gad", admin_user.user_id)

    adapter = store_adapter_upload(
        db_session,
        result.job.job_id,
        result.raw_upload_token,
        filename="adapter.zip",
        content=b"fake-adapter-bytes",
    )

    assert adapter.agent_id == "gad"
    assert adapter.job_id == result.job.job_id
    assert adapter.version == 1
    assert adapter.size_bytes == len(b"fake-adapter-bytes")

    refreshed_job = db_session.get(DpoTrainingJob, result.job.job_id)
    assert refreshed_job.status == "completed"
    assert refreshed_job.upload_used_at is not None


def test_store_adapter_upload_rejects_reuse(
    db_session, admin_user, tmp_path, monkeypatch
):
    monkeypatch.setattr("server.modules.training_data.adapters.ADAPTER_ROOT", tmp_path)
    _make_gad_generation(db_session, owner_id=admin_user.user_id)
    result = create_training_job(db_session, "gad", admin_user.user_id)

    store_adapter_upload(
        db_session,
        result.job.job_id,
        result.raw_upload_token,
        filename="adapter.zip",
        content=b"one",
    )

    with pytest.raises(TrainingJobNotFoundError):
        store_adapter_upload(
            db_session,
            result.job.job_id,
            result.raw_upload_token,
            filename="adapter.zip",
            content=b"two",
        )


def test_store_adapter_upload_rejects_wrong_token(
    db_session, admin_user, tmp_path, monkeypatch
):
    monkeypatch.setattr("server.modules.training_data.adapters.ADAPTER_ROOT", tmp_path)
    _make_gad_generation(db_session, owner_id=admin_user.user_id)
    result = create_training_job(db_session, "gad", admin_user.user_id)

    with pytest.raises(TrainingJobNotFoundError):
        store_adapter_upload(
            db_session,
            result.job.job_id,
            "wrong-token",
            filename="adapter.zip",
            content=b"one",
        )


def test_store_adapter_upload_rejects_bad_extension(
    db_session, admin_user, tmp_path, monkeypatch
):
    monkeypatch.setattr("server.modules.training_data.adapters.ADAPTER_ROOT", tmp_path)
    _make_gad_generation(db_session, owner_id=admin_user.user_id)
    result = create_training_job(db_session, "gad", admin_user.user_id)

    with pytest.raises(AdapterUploadError):
        store_adapter_upload(
            db_session,
            result.job.job_id,
            result.raw_upload_token,
            filename="adapter.exe",
            content=b"one",
        )


def test_store_adapter_upload_rejects_oversized_file(
    db_session, admin_user, tmp_path, monkeypatch
):
    monkeypatch.setattr("server.modules.training_data.adapters.ADAPTER_ROOT", tmp_path)
    monkeypatch.setattr(
        "server.modules.training_data.adapters.MAX_ADAPTER_UPLOAD_BYTES", 10
    )
    _make_gad_generation(db_session, owner_id=admin_user.user_id)
    result = create_training_job(db_session, "gad", admin_user.user_id)

    with pytest.raises(AdapterUploadError):
        store_adapter_upload(
            db_session,
            result.job.job_id,
            result.raw_upload_token,
            filename="adapter.zip",
            content=b"x" * 11,
        )


def test_list_trained_adapters_returns_newest_first(
    db_session, admin_user, tmp_path, monkeypatch
):
    monkeypatch.setattr("server.modules.training_data.adapters.ADAPTER_ROOT", tmp_path)
    _make_gad_generation(db_session, owner_id=admin_user.user_id)
    first = create_training_job(db_session, "gad", admin_user.user_id)
    store_adapter_upload(
        db_session,
        first.job.job_id,
        first.raw_upload_token,
        filename="a.zip",
        content=b"a",
    )

    second = create_training_job(db_session, "gad", admin_user.user_id)
    store_adapter_upload(
        db_session,
        second.job.job_id,
        second.raw_upload_token,
        filename="b.zip",
        content=b"b",
    )

    adapters = list_trained_adapters(db_session, "gad")
    assert [a.version for a in adapters] == [2, 1]
