"""apps/server/modules/training_data/jobs.py"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from server.modules.training_data.agents import VALID_AGENT_IDS, validate_agent_id
from server.modules.training_data.exceptions import (
    TrainingJobNotFoundError,
)
from server.modules.training_data.job_packages import (
    freeze_job_dataset,
    serialize_job_package_zip,
)
from server.modules.training_data.models import DpoTrainingJob
from server.modules.training_data.tokens import generate_raw_token, hash_token
from sqlalchemy.orm import Session


def _utc(value: datetime) -> datetime:
    """Normalize a possibly tz-naive datetime (e.g. read back from a
    SQLite test DB, which drops tzinfo) to UTC-aware for safe comparison."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


_DOWNLOAD_TOKEN_LIFETIME = timedelta(hours=24)
_UPLOAD_TOKEN_LIFETIME = timedelta(days=7)


@dataclass(frozen=True, slots=True)
class TrainingJobCreated:
    job: DpoTrainingJob
    raw_download_token: str
    raw_upload_token: str


def create_training_job(
    session: Session, agent_id: str, created_by: uuid.UUID
) -> TrainingJobCreated:
    """Create a training job: freeze the current DPO dataset for agent_id
    and mint a single-use download token plus a single-use upload token,
    both scoped to the new job."""
    validate_agent_id(agent_id)

    frozen = freeze_job_dataset(session, agent_id)

    raw_download_token = generate_raw_token()
    raw_upload_token = generate_raw_token()
    now = datetime.now(UTC)

    job = DpoTrainingJob(
        job_id=uuid.uuid4(),
        agent_id=agent_id,
        status="pending",
        created_by=created_by,
        pairs_content=frozen.pairs_content,
        provenance_content=frozen.provenance_content,
        manifest_json=frozen.manifest_json,
        download_token_hash=hash_token(raw_download_token),
        download_expires_at=now + _DOWNLOAD_TOKEN_LIFETIME,
        upload_token_hash=hash_token(raw_upload_token),
        upload_expires_at=now + _UPLOAD_TOKEN_LIFETIME,
    )
    session.add(job)
    session.commit()

    return TrainingJobCreated(
        job=job,
        raw_download_token=raw_download_token,
        raw_upload_token=raw_upload_token,
    )


def get_job_download_package(
    session: Session, job_id: uuid.UUID, raw_token: str
) -> bytes:
    """Validate the download token and return the frozen package as zip
    bytes. Raises TrainingJobNotFoundError for any invalid-token condition
    -- callers must map this to HTTP 404, never 403."""
    job = session.get(DpoTrainingJob, job_id)
    if job is None:
        raise TrainingJobNotFoundError("job not found")

    now = datetime.now(UTC)
    if (
        job.download_used_at is not None
        or _utc(job.download_expires_at) < now
        or hash_token(raw_token) != job.download_token_hash
    ):
        raise TrainingJobNotFoundError("invalid or expired download token")

    zip_bytes = serialize_job_package_zip(
        pairs_content=job.pairs_content,
        provenance_content=job.provenance_content,
        manifest_json=job.manifest_json,
    )

    job.download_used_at = now
    job.status = "downloaded"
    session.commit()

    return zip_bytes


def list_training_jobs(session: Session, agent_id: str) -> list[DpoTrainingJob]:
    return (
        session.query(DpoTrainingJob)
        .filter(DpoTrainingJob.agent_id == agent_id)
        .order_by(DpoTrainingJob.created_at.desc())
        .all()
    )


__all__ = [
    "VALID_AGENT_IDS",
    "TrainingJobCreated",
    "create_training_job",
    "get_job_download_package",
    "list_training_jobs",
]
