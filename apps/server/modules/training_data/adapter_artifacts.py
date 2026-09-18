"""Adapter artifact storage policies and filesystem operations."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

from server.modules.training_data.exceptions import AdapterUploadError
from server.modules.training_data.paths import (
    ADAPTER_ROOT,
    ALLOWED_ADAPTER_EXTENSIONS,
    MAX_ADAPTER_UPLOAD_BYTES,
)


@dataclass(frozen=True, slots=True)
class AdapterArtifact:
    adapter_id: uuid.UUID
    file_path: str
    file_sha256: str
    size_bytes: int


def validate_adapter_upload(filename: str, content: bytes) -> str:
    """Validate upload filename extension and content byte length.

    Returns the validated extension (lowercased, e.g. '.zip').
    Raises AdapterUploadError if invalid.
    """
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_ADAPTER_EXTENSIONS:
        raise AdapterUploadError(f"disallowed file extension: {extension!r}")
    if len(content) > MAX_ADAPTER_UPLOAD_BYTES:
        raise AdapterUploadError(
            f"file exceeds max size of {MAX_ADAPTER_UPLOAD_BYTES} bytes"
        )
    return extension


def get_adapter_target_dir(agent_id: str, adapter_id: uuid.UUID) -> Path:
    """Construct directory path for the adapter artifact under ADAPTER_ROOT."""
    return ADAPTER_ROOT / agent_id / str(adapter_id)


def write_adapter_artifact(
    agent_id: str,
    adapter_id: uuid.UUID,
    validated_extension: str,
    content: bytes,
) -> AdapterArtifact:
    """Write artifact bytes to disk using validated extension; return metadata."""
    target_dir = get_adapter_target_dir(agent_id, adapter_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"adapter{validated_extension}"
    target_path.write_bytes(content)

    return AdapterArtifact(
        adapter_id=adapter_id,
        file_path=str(target_path),
        file_sha256=hashlib.sha256(content).hexdigest(),
        size_bytes=len(content),
    )


__all__ = [
    "ALLOWED_ADAPTER_EXTENSIONS",
    "MAX_ADAPTER_UPLOAD_BYTES",
    "AdapterArtifact",
    "get_adapter_target_dir",
    "validate_adapter_upload",
    "write_adapter_artifact",
]
