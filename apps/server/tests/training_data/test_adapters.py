"""apps/server/tests/training_data/test_adapters.py"""

from __future__ import annotations

import io
import json
import zipfile

import pytest
from server.modules.training_data.adapters import (
    list_trained_adapters,
    store_adapter_upload,
)
from server.modules.training_data.exceptions import (
    AdapterUploadError,
    TrainingJobNotFoundError,
)
from server.modules.training_data.jobs import (
    create_training_job,
    get_job_download_package,
)
from server.modules.training_data.models import DpoTrainingJob
from server.tests.training_data.conftest import seed_eligible_dpo_pair


def _make_adapter_zip(
    source_manifest: dict,
    *,
    weights_filename: str = "adapter_model.safetensors",
    weights_content: bytes = b"lora-weights",
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "adapter_config.json", json.dumps({"base_model_name_or_path": "model"})
        )
        zf.writestr(
            "training_manifest.json",
            json.dumps({"source_job_manifest": source_manifest}),
        )
        zf.writestr(weights_filename, weights_content)
    return buffer.getvalue()


def test_store_adapter_upload_writes_file_and_row(
    db_session, admin_user, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.ADAPTER_ROOT",
        tmp_path,
    )
    seed_eligible_dpo_pair(db_session, owner_id=admin_user.user_id, agent_id="gad")
    result = create_training_job(db_session, "gad", admin_user.user_id)
    zip_bytes = _make_adapter_zip(result.job.manifest_json)

    adapter = store_adapter_upload(
        db_session,
        result.job.job_id,
        result.raw_upload_token,
        filename="adapter.zip",
        source=io.BytesIO(zip_bytes),
    )

    assert adapter.agent_id == "gad"
    assert adapter.job_id == result.job.job_id
    assert adapter.version == 1
    assert adapter.size_bytes == len(zip_bytes)

    refreshed_job = db_session.get(DpoTrainingJob, result.job.job_id)
    assert refreshed_job.status == "completed"
    assert refreshed_job.upload_used_at is not None


def test_store_adapter_upload_rejects_reuse(
    db_session, admin_user, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.ADAPTER_ROOT",
        tmp_path,
    )
    seed_eligible_dpo_pair(db_session, owner_id=admin_user.user_id, agent_id="gad")
    result = create_training_job(db_session, "gad", admin_user.user_id)
    zip_bytes = _make_adapter_zip(result.job.manifest_json)

    store_adapter_upload(
        db_session,
        result.job.job_id,
        result.raw_upload_token,
        filename="adapter.zip",
        source=io.BytesIO(zip_bytes),
    )

    with pytest.raises(TrainingJobNotFoundError):
        store_adapter_upload(
            db_session,
            result.job.job_id,
            result.raw_upload_token,
            filename="adapter.zip",
            source=io.BytesIO(zip_bytes),
        )


def test_store_adapter_upload_rejects_wrong_token(
    db_session, admin_user, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.ADAPTER_ROOT",
        tmp_path,
    )
    seed_eligible_dpo_pair(db_session, owner_id=admin_user.user_id, agent_id="gad")
    result = create_training_job(db_session, "gad", admin_user.user_id)
    zip_bytes = _make_adapter_zip(result.job.manifest_json)

    with pytest.raises(TrainingJobNotFoundError):
        store_adapter_upload(
            db_session,
            result.job.job_id,
            "wrong-token",
            filename="adapter.zip",
            source=io.BytesIO(zip_bytes),
        )


def test_store_adapter_upload_rejects_bad_extension(
    db_session, admin_user, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.ADAPTER_ROOT",
        tmp_path,
    )
    seed_eligible_dpo_pair(db_session, owner_id=admin_user.user_id, agent_id="gad")
    result = create_training_job(db_session, "gad", admin_user.user_id)

    next_version_called = False
    from server.modules.training_data import adapters

    original_next_version = adapters._next_version

    def _spy_next_version(*args, **kwargs):
        nonlocal next_version_called
        next_version_called = True
        return original_next_version(*args, **kwargs)

    monkeypatch.setattr(
        "server.modules.training_data.adapters._next_version", _spy_next_version
    )

    with pytest.raises(AdapterUploadError):
        store_adapter_upload(
            db_session,
            result.job.job_id,
            result.raw_upload_token,
            filename="adapter.exe",
            source=io.BytesIO(b"one"),
        )

    assert not next_version_called
    staging_dir = tmp_path / ".staging"
    assert not staging_dir.exists() or list(staging_dir.iterdir()) == []


def test_store_adapter_upload_rejects_oversized_stream_and_cleans_up(
    db_session, admin_user, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.ADAPTER_ROOT",
        tmp_path,
    )
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.MAX_ADAPTER_UPLOAD_BYTES",
        20,
    )
    seed_eligible_dpo_pair(db_session, owner_id=admin_user.user_id, agent_id="gad")
    result = create_training_job(db_session, "gad", admin_user.user_id)

    next_version_called = False
    from server.modules.training_data import adapters

    original_next_version = adapters._next_version

    def _spy_next_version(*args, **kwargs):
        nonlocal next_version_called
        next_version_called = True
        return original_next_version(*args, **kwargs)

    monkeypatch.setattr(
        "server.modules.training_data.adapters._next_version", _spy_next_version
    )

    with pytest.raises(AdapterUploadError) as exc_info:
        store_adapter_upload(
            db_session,
            result.job.job_id,
            result.raw_upload_token,
            filename="adapter.zip",
            source=io.BytesIO(b"x" * 100),
        )

    assert "file exceeds max size" in str(exc_info.value)
    assert not next_version_called
    staging_dir = tmp_path / ".staging"
    assert not staging_dir.exists() or list(staging_dir.iterdir()) == []


def test_upload_before_download_and_completed_not_regressed(
    db_session, admin_user, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.ADAPTER_ROOT",
        tmp_path,
    )
    seed_eligible_dpo_pair(db_session, owner_id=admin_user.user_id, agent_id="gad")
    result = create_training_job(db_session, "gad", admin_user.user_id)
    zip_bytes = _make_adapter_zip(result.job.manifest_json)

    # Upload while pending, before Colab consumes the download token.
    adapter = store_adapter_upload(
        db_session,
        result.job.job_id,
        result.raw_upload_token,
        filename="adapter.zip",
        source=io.BytesIO(zip_bytes),
    )
    assert adapter is not None

    job = db_session.get(DpoTrainingJob, result.job.job_id)
    assert job.status == "completed"

    # A later download must not regress completed back to downloaded.
    pkg = get_job_download_package(
        db_session,
        result.job.job_id,
        result.raw_download_token,
    )
    assert len(pkg) > 0

    refreshed = db_session.get(DpoTrainingJob, result.job.job_id)
    assert refreshed.status == "completed"
    assert refreshed.download_used_at is not None


def test_list_trained_adapters_returns_newest_first(
    db_session, admin_user, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.ADAPTER_ROOT",
        tmp_path,
    )
    seed_eligible_dpo_pair(db_session, owner_id=admin_user.user_id, agent_id="gad")
    first = create_training_job(db_session, "gad", admin_user.user_id)
    first_zip = _make_adapter_zip(first.job.manifest_json)
    store_adapter_upload(
        db_session,
        first.job.job_id,
        first.raw_upload_token,
        filename="a.zip",
        source=io.BytesIO(first_zip),
    )

    second = create_training_job(db_session, "gad", admin_user.user_id)
    second_zip = _make_adapter_zip(second.job.manifest_json)
    store_adapter_upload(
        db_session,
        second.job.job_id,
        second.raw_upload_token,
        filename="b.zip",
        source=io.BytesIO(second_zip),
    )

    adapters = list_trained_adapters(db_session, "gad")
    assert [a.version for a in adapters] == [2, 1]


def test_concurrent_upload_retries_on_version_conflict(
    db_session, admin_user, tmp_path, monkeypatch
):
    """Simulate a race where another job commits version N concurrently."""
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.ADAPTER_ROOT",
        tmp_path,
    )
    seed_eligible_dpo_pair(db_session, owner_id=admin_user.user_id, agent_id="gad")
    first = create_training_job(db_session, "gad", admin_user.user_id)
    second = create_training_job(db_session, "gad", admin_user.user_id)

    first_zip = _make_adapter_zip(first.job.manifest_json)
    second_zip = _make_adapter_zip(second.job.manifest_json)

    from server.modules.training_data import adapters

    original_next_version = adapters._next_version
    call_count = 0

    def raceway_next_version(session, agent_id):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # On the first call, pretend it read version 1 (which will be true),
            # but right before this upload finishes, the first job uploads version 1.
            store_adapter_upload(
                session,
                first.job.job_id,
                first.raw_upload_token,
                filename="first.zip",
                source=io.BytesIO(first_zip),
            )
            # Intentionally return 1 to simulate having computed version 1
            # before the collision.
            return 1
        return original_next_version(session, agent_id)

    monkeypatch.setattr(
        "server.modules.training_data.adapters._next_version",
        raceway_next_version,
    )

    # Now uploading `second` encounters the duplicate version 1,
    # catches IntegrityError within savepoint, retries, and stores as version 2.
    adapter2 = store_adapter_upload(
        db_session,
        second.job.job_id,
        second.raw_upload_token,
        filename="second.zip",
        source=io.BytesIO(second_zip),
    )

    assert adapter2.version == 2
    assert adapter2.job_id == second.job.job_id

    # Verify both jobs are completed and both adapters exist with distinct versions
    first_job = db_session.get(DpoTrainingJob, first.job.job_id)
    second_job = db_session.get(DpoTrainingJob, second.job.job_id)
    assert first_job.status == "completed"
    assert second_job.status == "completed"

    all_adapters = list_trained_adapters(db_session, "gad")
    assert len(all_adapters) == 2
    assert [a.version for a in all_adapters] == [2, 1]


def test_unique_agent_version_model_constraint(db_session, admin_user):
    """Verify TrainedAdapter rejects duplicate (agent_id, version) at DB level."""
    from uuid import uuid4

    from server.modules.training_data.models import TrainedAdapter
    from sqlalchemy.exc import IntegrityError

    seed_eligible_dpo_pair(db_session, owner_id=admin_user.user_id, agent_id="gad")
    first = create_training_job(db_session, "gad", admin_user.user_id)
    second = create_training_job(db_session, "gad", admin_user.user_id)

    a1 = TrainedAdapter(
        adapter_id=uuid4(),
        agent_id="gad",
        job_id=first.job.job_id,
        version=1,
        file_path="/path/1",
        file_sha256="sha1",
        size_bytes=100,
    )
    db_session.add(a1)
    db_session.commit()

    a2 = TrainedAdapter(
        adapter_id=uuid4(),
        agent_id="gad",
        job_id=second.job.job_id,
        version=1,
        file_path="/path/2",
        file_sha256="sha2",
        size_bytes=200,
    )
    db_session.add(a2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_store_adapter_upload_preserves_published_file_on_commit_failure(
    db_session, admin_user, tmp_path, monkeypatch
):
    """If commit fails / has ambiguous outcome, the published file is NOT deleted."""
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.ADAPTER_ROOT",
        tmp_path,
    )
    seed_eligible_dpo_pair(db_session, owner_id=admin_user.user_id, agent_id="gad")
    result = create_training_job(db_session, "gad", admin_user.user_id)
    zip_bytes = _make_adapter_zip(result.job.manifest_json)

    def failing_commit():
        raise RuntimeError("database transport broke during commit ack")

    monkeypatch.setattr(db_session, "commit", failing_commit)

    with pytest.raises(
        RuntimeError, match="database transport broke during commit ack"
    ):
        store_adapter_upload(
            db_session,
            result.job.job_id,
            result.raw_upload_token,
            filename="adapter.zip",
            source=io.BytesIO(zip_bytes),
        )

    # Artifact must NOT be deleted
    agent_dir = tmp_path / "gad"
    published_files = list(agent_dir.glob("*/adapter.zip"))
    assert len(published_files) == 1
    assert published_files[0].read_bytes() == zip_bytes
