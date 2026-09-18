"""apps/server/modules/training_data/adapters.py"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from server.modules.training_data.adapter_artifacts import (
    validate_adapter_upload,
    write_adapter_artifact,
)
from server.modules.training_data.exceptions import (
    TrainingJobNotFoundError,
)
from server.modules.training_data.jobs import _utc
from server.modules.training_data.models import DpoTrainingJob, TrainedAdapter
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

    validated_extension = validate_adapter_upload(filename, content)

    version = _next_version(session, job.agent_id)
    adapter_id = uuid.uuid4()
    artifact = write_adapter_artifact(
        job.agent_id, adapter_id, validated_extension, content
    )

    adapter = TrainedAdapter(
        adapter_id=artifact.adapter_id,
        agent_id=job.agent_id,
        job_id=job.job_id,
        version=version,
        file_path=artifact.file_path,
        file_sha256=artifact.file_sha256,
        size_bytes=artifact.size_bytes,
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


__all__ = [
    "list_trained_adapters",
    "store_adapter_upload",
]
