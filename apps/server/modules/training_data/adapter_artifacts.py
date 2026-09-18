"""Bounded validation and filesystem storage for uploaded adapter artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import uuid
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from server.modules.training_data.exceptions import AdapterUploadError
from server.modules.training_data.paths import (
    ADAPTER_ROOT,
    ALLOWED_ADAPTER_EXTENSIONS,
    MAX_ADAPTER_UPLOAD_BYTES,
)

_STREAM_CHUNK_BYTES = 1024 * 1024
_MAX_ARCHIVE_MEMBER_COUNT = 100
_MAX_ARCHIVE_MEMBER_BYTES = MAX_ADAPTER_UPLOAD_BYTES
_MAX_ARCHIVE_UNCOMPRESSED_BYTES = MAX_ADAPTER_UPLOAD_BYTES * 2
_MAX_JSON_MEMBER_BYTES = 1024 * 1024
_REQUIRED_ROOT_MEMBERS = {"adapter_config.json", "training_manifest.json"}
_SUPPORTED_WEIGHT_MEMBERS = {"adapter_model.safetensors", "adapter_model.bin"}


@dataclass(frozen=True, slots=True)
class AdapterArtifact:
    adapter_id: uuid.UUID
    file_path: str
    file_sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class StagedAdapterArtifact:
    adapter_id: uuid.UUID
    staging_path: Path
    final_path: Path
    file_sha256: str
    size_bytes: int


def _validated_extension(filename: str) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_ADAPTER_EXTENSIONS:
        raise AdapterUploadError(f"disallowed file extension: {extension!r}")
    return extension


def get_adapter_target_dir(agent_id: str, adapter_id: uuid.UUID) -> Path:
    """Construct the final directory under the configured adapter root."""
    return ADAPTER_ROOT / agent_id / str(adapter_id)


def _safe_member_name(name: str) -> bool:
    if not name or "\\" in name or name.startswith("/"):
        return False
    path = PurePosixPath(name)
    return not path.is_absolute() and all(
        part not in {"", ".", ".."} for part in path.parts
    )


def _load_bounded_json(zf: zipfile.ZipFile, info: zipfile.ZipInfo) -> dict:
    if info.file_size > _MAX_JSON_MEMBER_BYTES:
        raise AdapterUploadError(f"archive member {info.filename!r} is too large")
    try:
        raw_bytes = zf.read(info)
    except (
        zipfile.BadZipFile,
        zlib.error,
        EOFError,
        OSError,
        RuntimeError,
    ) as exc:
        raise AdapterUploadError(
            f"failed to read archive member {info.filename!r}: {exc}"
        ) from exc
    try:
        value = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RuntimeError) as exc:
        raise AdapterUploadError(
            f"archive member {info.filename!r} is not valid JSON"
        ) from exc
    if not isinstance(value, dict):
        raise AdapterUploadError(
            f"archive member {info.filename!r} must contain a JSON object"
        )
    return value


def _validate_archive(path: Path, expected_source_manifest: dict) -> None:
    try:
        with zipfile.ZipFile(path) as zf:
            member_count = len(zf.namelist())
            if member_count > _MAX_ARCHIVE_MEMBER_COUNT:
                raise AdapterUploadError(
                    f"adapter archive contains too many members: "
                    f"{member_count} > {_MAX_ARCHIVE_MEMBER_COUNT}"
                )

            infos = [info for info in zf.infolist() if not info.is_dir()]
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                raise AdapterUploadError("adapter archive contains duplicate members")

            total_uncompressed = 0
            by_name: dict[str, zipfile.ZipInfo] = {}
            for info in infos:
                if not _safe_member_name(info.filename):
                    raise AdapterUploadError(
                        f"unsafe adapter archive member: {info.filename!r}"
                    )
                if info.flag_bits & 0x1:
                    raise AdapterUploadError(
                        "encrypted adapter archives are not allowed"
                    )
                mode = (info.external_attr >> 16) & 0o170000
                if mode == stat.S_IFLNK:
                    raise AdapterUploadError("adapter archive symlinks are not allowed")
                if info.file_size > _MAX_ARCHIVE_MEMBER_BYTES:
                    raise AdapterUploadError(
                        f"archive member {info.filename!r} exceeds the size limit"
                    )
                total_uncompressed += info.file_size
                if total_uncompressed > _MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                    raise AdapterUploadError(
                        "adapter archive uncompressed content exceeds the size limit"
                    )
                by_name[info.filename] = info

            missing = _REQUIRED_ROOT_MEMBERS - by_name.keys()
            if missing:
                raise AdapterUploadError(
                    f"adapter archive is missing required files: {sorted(missing)}"
                )
            weights = _SUPPORTED_WEIGHT_MEMBERS & by_name.keys()
            if len(weights) != 1:
                raise AdapterUploadError(
                    "adapter archive must contain exactly one supported weight file"
                )

            _load_bounded_json(zf, by_name["adapter_config.json"])
            training_manifest = _load_bounded_json(
                zf, by_name["training_manifest.json"]
            )
            if training_manifest.get("source_job_manifest") != expected_source_manifest:
                raise AdapterUploadError(
                    "training manifest does not match the frozen source job manifest"
                )

            corrupt_member = zf.testzip()
            if corrupt_member is not None:
                raise AdapterUploadError(
                    f"adapter archive member failed CRC validation: {corrupt_member!r}"
                )
    except zipfile.BadZipFile as exc:
        raise AdapterUploadError(
            "uploaded artifact is not a valid ZIP archive"
        ) from exc
    except (zlib.error, EOFError, OSError, RuntimeError) as exc:
        raise AdapterUploadError(
            f"failed to read or decompress adapter archive: {exc}"
        ) from exc


def stage_adapter_artifact(
    agent_id: str,
    adapter_id: uuid.UUID,
    *,
    filename: str,
    source: BinaryIO,
    expected_source_manifest: dict,
) -> StagedAdapterArtifact:
    """Copy an untrusted upload into bounded staging and validate its archive."""
    extension = _validated_extension(filename)
    staging_dir = ADAPTER_ROOT / ".staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    staging_path = staging_dir / f"{adapter_id}{extension}.part"
    final_path = get_adapter_target_dir(agent_id, adapter_id) / f"adapter{extension}"

    digest = hashlib.sha256()
    size_bytes = 0
    try:
        with staging_path.open("xb") as destination:
            while True:
                chunk = source.read(_STREAM_CHUNK_BYTES)
                if not chunk:
                    break
                if not isinstance(chunk, bytes):
                    raise AdapterUploadError(
                        "adapter upload stream returned non-bytes data"
                    )
                size_bytes += len(chunk)
                if size_bytes > MAX_ADAPTER_UPLOAD_BYTES:
                    raise AdapterUploadError(
                        f"file exceeds max size of {MAX_ADAPTER_UPLOAD_BYTES} bytes"
                    )
                digest.update(chunk)
                destination.write(chunk)
            destination.flush()
            os.fsync(destination.fileno())

        _validate_archive(staging_path, expected_source_manifest)
        return StagedAdapterArtifact(
            adapter_id=adapter_id,
            staging_path=staging_path,
            final_path=final_path,
            file_sha256=digest.hexdigest(),
            size_bytes=size_bytes,
        )
    except Exception:
        staging_path.unlink(missing_ok=True)
        raise


def publish_staged_adapter(staged: StagedAdapterArtifact) -> AdapterArtifact:
    """Atomically publish a validated staged artifact on the same filesystem."""
    staged.final_path.parent.mkdir(parents=True, exist_ok=False)
    try:
        os.replace(staged.staging_path, staged.final_path)
    except Exception:
        try:
            staged.final_path.parent.rmdir()
        except OSError:
            pass
        raise
    return AdapterArtifact(
        adapter_id=staged.adapter_id,
        file_path=str(staged.final_path),
        file_sha256=staged.file_sha256,
        size_bytes=staged.size_bytes,
    )


def discard_staged_adapter(staged: StagedAdapterArtifact) -> None:
    staged.staging_path.unlink(missing_ok=True)


def remove_published_adapter(path: str) -> None:
    artifact_path = Path(path)
    artifact_path.unlink(missing_ok=True)
    try:
        artifact_path.parent.rmdir()
    except OSError:
        pass


__all__ = [
    "ALLOWED_ADAPTER_EXTENSIONS",
    "MAX_ADAPTER_UPLOAD_BYTES",
    "AdapterArtifact",
    "StagedAdapterArtifact",
    "discard_staged_adapter",
    "get_adapter_target_dir",
    "publish_staged_adapter",
    "remove_published_adapter",
    "stage_adapter_artifact",
]
