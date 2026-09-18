"""apps/server/modules/training_data/adapters.py"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path

from server.modules.training_data.exceptions import (
    AdapterUploadError,
    TrainingJobNotFoundError,
)
from server.modules.training_data.jobs import _utc
from server.modules.training_data.models import DpoTrainingJob, TrainedAdapter
from server.modules.training_data.paths import (
    ADAPTER_ROOT,
    ALLOWED_ADAPTER_EXTENSIONS,
    MAX_ADAPTER_UPLOAD_BYTES,
)
from server.modules.training_data.tokens import hash_token
from sqlalchemy import func
from sqlalchemy.orm import Session


def _next_version(session: Session, agent_id: str) -> int:
    current_max = (
        session.query(func.max(TrainedAdapter.version))
        .filter(TrainedAdapter.agent_id == agent_id)
        .scalar()
    )
    return (current_max or 0) + 1


def store_adapter_upload(
    session: Session,
    job_id: uuid.UUID,
    raw_token: str,
    *,
    filename: str,
    content: bytes,
) -> TrainedAdapter:
    """Validate the upload token, persist the adapter file, and record a
    TrainedAdapter row. Raises TrainingJobNotFoundError for any
    invalid-token condition (callers map this to HTTP 404) or
    AdapterUploadError for a valid token with a disallowed file."""
    job = session.get(DpoTrainingJob, job_id)
    if job is None:
        raise TrainingJobNotFoundError("job not found")

    now = datetime.now(UTC)
    if (
        job.upload_used_at is not None
        or _utc(job.upload_expires_at) < now
        or hash_token(raw_token) != job.upload_token_hash
    ):
        raise TrainingJobNotFoundError("invalid or expired upload token")

    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_ADAPTER_EXTENSIONS:
        raise AdapterUploadError(f"disallowed file extension: {extension!r}")
    if len(content) > MAX_ADAPTER_UPLOAD_BYTES:
        raise AdapterUploadError(
            f"file exceeds max size of {MAX_ADAPTER_UPLOAD_BYTES} bytes"
        )

    version = _next_version(session, job.agent_id)
    adapter_id = uuid.uuid4()
    target_dir = ADAPTER_ROOT / job.agent_id / str(adapter_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"adapter{extension}"
    target_path.write_bytes(content)

    adapter = TrainedAdapter(
        adapter_id=adapter_id,
        agent_id=job.agent_id,
        job_id=job.job_id,
        version=version,
        file_path=str(target_path),
        file_sha256=hashlib.sha256(content).hexdigest(),
        size_bytes=len(content),
    )
    session.add(adapter)

    job.upload_used_at = now
    job.status = "completed"

    session.commit()
    return adapter


def list_trained_adapters(session: Session, agent_id: str) -> list[TrainedAdapter]:
    return (
        session.query(TrainedAdapter)
        .filter(TrainedAdapter.agent_id == agent_id)
        .order_by(TrainedAdapter.version.desc())
        .all()
    )


__all__ = ["store_adapter_upload", "list_trained_adapters"]
