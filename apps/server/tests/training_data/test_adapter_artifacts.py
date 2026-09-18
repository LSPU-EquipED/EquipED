from __future__ import annotations

import uuid

import pytest
from server.modules.training_data.adapter_artifacts import (
    ALLOWED_ADAPTER_EXTENSIONS,
    MAX_ADAPTER_UPLOAD_BYTES,
    AdapterArtifact,
    get_adapter_target_dir,
    validate_adapter_upload,
    write_adapter_artifact,
)
from server.modules.training_data.exceptions import AdapterUploadError


def test_allowed_extensions_constant():
    assert ".zip" in ALLOWED_ADAPTER_EXTENSIONS


def test_validate_adapter_upload_accepts_valid_file():
    ext = validate_adapter_upload("model_weights.zip", b"zipcontent")
    assert ext == ".zip"


def test_validate_adapter_upload_rejects_bad_extension():
    with pytest.raises(AdapterUploadError) as exc_info:
        validate_adapter_upload("model_weights.tar.gz", b"content")
    assert "disallowed file extension" in str(exc_info.value)


def test_validate_adapter_upload_rejects_oversized_file(monkeypatch):
    assert MAX_ADAPTER_UPLOAD_BYTES > 0
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.MAX_ADAPTER_UPLOAD_BYTES",
        10,
    )
    with pytest.raises(AdapterUploadError) as exc_info:
        validate_adapter_upload("adapter.zip", b"x" * 11)
    assert "file exceeds max size" in str(exc_info.value)


def test_get_adapter_target_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.ADAPTER_ROOT",
        tmp_path,
    )
    adapter_id = uuid.uuid4()
    target_dir = get_adapter_target_dir("gad", adapter_id)
    assert target_dir == tmp_path / "gad" / str(adapter_id)


def test_write_adapter_artifact(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.ADAPTER_ROOT",
        tmp_path,
    )
    adapter_id = uuid.uuid4()
    content = b"my-binary-adapter-content"
    artifact = write_adapter_artifact("gad", adapter_id, ".zip", content)

    assert isinstance(artifact, AdapterArtifact)
    assert artifact.adapter_id == adapter_id
    assert artifact.size_bytes == len(content)
    assert artifact.file_path == str(tmp_path / "gad" / str(adapter_id) / "adapter.zip")

    target_file = tmp_path / "gad" / str(adapter_id) / "adapter.zip"
    assert target_file.is_file()
    assert target_file.read_bytes() == content
