from __future__ import annotations

import io
import json
import stat
import uuid
import zipfile
import zlib

import pytest
from server.modules.training_data.adapter_artifacts import (
    ALLOWED_ADAPTER_EXTENSIONS,
    AdapterArtifact,
    StagedAdapterArtifact,
    discard_staged_adapter,
    get_adapter_target_dir,
    publish_staged_adapter,
    remove_published_adapter,
    stage_adapter_artifact,
)
from server.modules.training_data.exceptions import AdapterUploadError


def _make_adapter_zip_bytes(
    source_manifest: dict,
    *,
    adapter_config: dict | None = None,
    weights_filename: str = "adapter_model.safetensors",
    weights_content: bytes = b"weights-payload",
    include_training_manifest: bool = True,
    include_adapter_config: bool = True,
    include_weights: bool = True,
    custom_members: dict[str, bytes] | None = None,
    symlink_member: tuple[str, str] | None = None,
    duplicate_member: tuple[str, bytes] | None = None,
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if include_adapter_config:
            cfg = (
                adapter_config
                if adapter_config is not None
                else {"base_model_name_or_path": "model"}
            )
            zf.writestr("adapter_config.json", json.dumps(cfg))

        if include_training_manifest:
            manifest_data = {"source_job_manifest": source_manifest}
            zf.writestr("training_manifest.json", json.dumps(manifest_data))

        if include_weights:
            zf.writestr(weights_filename, weights_content)

        if custom_members:
            for name, content in custom_members.items():
                zf.writestr(name, content)

        if symlink_member:
            name, target = symlink_member
            info = zipfile.ZipInfo(name)
            info.create_system = 3  # Unix
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            zf.writestr(info, target)

        if duplicate_member:
            name, content = duplicate_member
            zf.writestr(name, content)
            zf.writestr(name, content)

    return buffer.getvalue()


def test_allowed_extensions_constant():
    assert ".zip" in ALLOWED_ADAPTER_EXTENSIONS


def test_get_adapter_target_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.ADAPTER_ROOT",
        tmp_path,
    )
    adapter_id = uuid.uuid4()
    target_dir = get_adapter_target_dir("gad", adapter_id)
    assert target_dir == tmp_path / "gad" / str(adapter_id)


def test_stage_adapter_artifact_happy_path(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.ADAPTER_ROOT",
        tmp_path,
    )
    adapter_id = uuid.uuid4()
    manifest = {"agent_id": "gad", "pair_count": 1}
    zip_bytes = _make_adapter_zip_bytes(manifest)

    staged = stage_adapter_artifact(
        "gad",
        adapter_id,
        filename="adapter.zip",
        source=io.BytesIO(zip_bytes),
        expected_source_manifest=manifest,
    )

    assert isinstance(staged, StagedAdapterArtifact)
    assert staged.adapter_id == adapter_id
    assert staged.size_bytes == len(zip_bytes)
    assert staged.staging_path.exists()
    assert not staged.final_path.exists()

    artifact = publish_staged_adapter(staged)
    assert isinstance(artifact, AdapterArtifact)
    assert artifact.adapter_id == adapter_id
    assert not staged.staging_path.exists()
    assert staged.final_path.exists()
    assert staged.final_path.read_bytes() == zip_bytes

    remove_published_adapter(artifact.file_path)
    assert not staged.final_path.exists()


def test_stage_adapter_artifact_rejects_bad_extension():
    with pytest.raises(AdapterUploadError) as exc_info:
        stage_adapter_artifact(
            "gad",
            uuid.uuid4(),
            filename="model_weights.tar.gz",
            source=io.BytesIO(b"content"),
            expected_source_manifest={},
        )
    assert "disallowed file extension" in str(exc_info.value)


def test_stage_adapter_artifact_bounded_streaming_oversized(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.ADAPTER_ROOT",
        tmp_path,
    )
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.MAX_ADAPTER_UPLOAD_BYTES",
        20,
    )
    adapter_id = uuid.uuid4()

    class MonitoredStream(io.BytesIO):
        def __init__(self, data):
            super().__init__(data)
            self.total_read = 0

        def read(self, size=-1):
            chunk = super().read(size)
            self.total_read += len(chunk)
            return chunk

    stream = MonitoredStream(b"x" * 100)

    with pytest.raises(AdapterUploadError) as exc_info:
        stage_adapter_artifact(
            "gad",
            adapter_id,
            filename="adapter.zip",
            source=stream,
            expected_source_manifest={},
        )
    assert "file exceeds max size" in str(exc_info.value)

    # Staging cleanup verified
    staging_dir = tmp_path / ".staging"
    staged_files = list(staging_dir.iterdir()) if staging_dir.exists() else []
    assert staged_files == []


def test_stage_adapter_artifact_rejects_not_a_zip(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.ADAPTER_ROOT",
        tmp_path,
    )
    adapter_id = uuid.uuid4()
    with pytest.raises(AdapterUploadError) as exc_info:
        stage_adapter_artifact(
            "gad",
            adapter_id,
            filename="adapter.zip",
            source=io.BytesIO(b"not a real zip file"),
            expected_source_manifest={},
        )
    assert "not a valid ZIP archive" in str(exc_info.value)
    assert not (tmp_path / ".staging" / f"{adapter_id}.zip.part").exists()


def test_stage_adapter_artifact_rejects_path_traversal(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.ADAPTER_ROOT",
        tmp_path,
    )
    manifest = {"agent_id": "gad"}
    zip_bytes = _make_adapter_zip_bytes(
        manifest,
        custom_members={"../evil.txt": b"evil"},
    )
    with pytest.raises(AdapterUploadError) as exc_info:
        stage_adapter_artifact(
            "gad",
            uuid.uuid4(),
            filename="adapter.zip",
            source=io.BytesIO(zip_bytes),
            expected_source_manifest=manifest,
        )
    assert "unsafe adapter archive member" in str(exc_info.value)


def test_stage_adapter_artifact_rejects_symlinks(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.ADAPTER_ROOT",
        tmp_path,
    )
    manifest = {"agent_id": "gad"}
    zip_bytes = _make_adapter_zip_bytes(
        manifest,
        symlink_member=("link_to_etc", "/etc/passwd"),
    )
    with pytest.raises(AdapterUploadError) as exc_info:
        stage_adapter_artifact(
            "gad",
            uuid.uuid4(),
            filename="adapter.zip",
            source=io.BytesIO(zip_bytes),
            expected_source_manifest=manifest,
        )
    assert "symlinks are not allowed" in str(exc_info.value)


def test_stage_adapter_artifact_rejects_duplicate_members(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.ADAPTER_ROOT",
        tmp_path,
    )
    manifest = {"agent_id": "gad"}
    zip_bytes = _make_adapter_zip_bytes(
        manifest,
        duplicate_member=("extra.txt", b"foo"),
    )
    with pytest.raises(AdapterUploadError) as exc_info:
        stage_adapter_artifact(
            "gad",
            uuid.uuid4(),
            filename="adapter.zip",
            source=io.BytesIO(zip_bytes),
            expected_source_manifest=manifest,
        )
    assert "duplicate members" in str(exc_info.value)


def test_stage_adapter_artifact_rejects_missing_required_files(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.ADAPTER_ROOT",
        tmp_path,
    )
    manifest = {"agent_id": "gad"}
    zip_bytes = _make_adapter_zip_bytes(
        manifest,
        include_adapter_config=False,
    )
    with pytest.raises(AdapterUploadError) as exc_info:
        stage_adapter_artifact(
            "gad",
            uuid.uuid4(),
            filename="adapter.zip",
            source=io.BytesIO(zip_bytes),
            expected_source_manifest=manifest,
        )
    assert "missing required files" in str(exc_info.value)


def test_stage_adapter_artifact_rejects_multiple_or_missing_weights(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.ADAPTER_ROOT",
        tmp_path,
    )
    manifest = {"agent_id": "gad"}
    no_weights_zip = _make_adapter_zip_bytes(manifest, include_weights=False)
    with pytest.raises(AdapterUploadError) as exc_info:
        stage_adapter_artifact(
            "gad",
            uuid.uuid4(),
            filename="adapter.zip",
            source=io.BytesIO(no_weights_zip),
            expected_source_manifest=manifest,
        )
    assert "exactly one supported weight file" in str(exc_info.value)

    multi_weights_zip = _make_adapter_zip_bytes(
        manifest,
        custom_members={"adapter_model.bin": b"bin-weights"},
    )
    with pytest.raises(AdapterUploadError) as exc_info:
        stage_adapter_artifact(
            "gad",
            uuid.uuid4(),
            filename="adapter.zip",
            source=io.BytesIO(multi_weights_zip),
            expected_source_manifest=manifest,
        )
    assert "exactly one supported weight file" in str(exc_info.value)


def test_stage_adapter_artifact_rejects_manifest_mismatch(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.ADAPTER_ROOT",
        tmp_path,
    )
    manifest = {"agent_id": "gad", "pair_count": 5}
    mismatched_manifest = {"agent_id": "gad", "pair_count": 999}
    zip_bytes = _make_adapter_zip_bytes(manifest)

    with pytest.raises(AdapterUploadError) as exc_info:
        stage_adapter_artifact(
            "gad",
            uuid.uuid4(),
            filename="adapter.zip",
            source=io.BytesIO(zip_bytes),
            expected_source_manifest=mismatched_manifest,
        )
    assert "training manifest does not match" in str(exc_info.value)


def test_stage_adapter_artifact_rejects_corrupt_zip(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.ADAPTER_ROOT",
        tmp_path,
    )
    manifest = {"agent_id": "gad"}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("adapter_config.json", json.dumps({"a": 1}))
        zf.writestr(
            "training_manifest.json", json.dumps({"source_job_manifest": manifest})
        )
        zf.writestr("adapter_model.safetensors", b"real-weights-data")
    zip_bytes = buffer.getvalue()

    corrupt_bytes = zip_bytes.replace(b"real-weights-data", b"bad1-weights-data")
    assert corrupt_bytes != zip_bytes

    with pytest.raises(AdapterUploadError) as exc_info:
        stage_adapter_artifact(
            "gad",
            uuid.uuid4(),
            filename="adapter.zip",
            source=io.BytesIO(corrupt_bytes),
            expected_source_manifest=manifest,
        )
    assert "CRC validation" in str(exc_info.value) or "not a valid ZIP archive" in str(
        exc_info.value
    )


def test_discard_staged_adapter(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.ADAPTER_ROOT",
        tmp_path,
    )
    manifest = {"agent_id": "gad"}
    zip_bytes = _make_adapter_zip_bytes(manifest)
    adapter_id = uuid.uuid4()
    staged = stage_adapter_artifact(
        "gad",
        adapter_id,
        filename="adapter.zip",
        source=io.BytesIO(zip_bytes),
        expected_source_manifest=manifest,
    )
    assert staged.staging_path.exists()
    discard_staged_adapter(staged)
    assert not staged.staging_path.exists()


def test_stage_adapter_artifact_rejects_excessive_member_count(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.ADAPTER_ROOT",
        tmp_path,
    )
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts._MAX_ARCHIVE_MEMBER_COUNT",
        5,
    )
    manifest = {"agent_id": "gad"}
    extra_members = {f"file_{i}.txt": b"x" for i in range(10)}
    zip_bytes = _make_adapter_zip_bytes(manifest, custom_members=extra_members)

    with pytest.raises(AdapterUploadError) as exc_info:
        stage_adapter_artifact(
            "gad",
            uuid.uuid4(),
            filename="adapter.zip",
            source=io.BytesIO(zip_bytes),
            expected_source_manifest=manifest,
        )
    assert "contains too many members" in str(exc_info.value)


@pytest.mark.parametrize(
    "failure",
    [zlib.error("corrupted compressed stream"), NotImplementedError("codec")],
)
def test_stage_adapter_artifact_translates_decompression_error(
    monkeypatch, tmp_path, failure
):
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.ADAPTER_ROOT",
        tmp_path,
    )
    manifest = {"agent_id": "gad"}
    zip_bytes = _make_adapter_zip_bytes(manifest)

    # Simulate decompression failures during CRC validation.
    def _broken_testzip(self):
        raise failure

    monkeypatch.setattr(zipfile.ZipFile, "testzip", _broken_testzip)

    with pytest.raises(AdapterUploadError) as exc_info:
        stage_adapter_artifact(
            "gad",
            uuid.uuid4(),
            filename="adapter.zip",
            source=io.BytesIO(zip_bytes),
            expected_source_manifest=manifest,
        )
    assert "failed to read or decompress" in str(exc_info.value)
