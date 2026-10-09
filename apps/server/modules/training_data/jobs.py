"""apps/server/modules/training_data/jobs.py"""

from __future__ import annotations

import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from server.modules.training_data.agents import VALID_AGENT_IDS, validate_agent_id
from server.modules.training_data.exceptions import (
    EmptyTrainingDatasetError,
    TrainingJobNotFoundError,
)
from server.modules.training_data.job_packages import (
    freeze_job_dataset,
    serialize_job_package_zip,
)
from server.modules.training_data.models import DpoTrainingJob
from server.modules.training_data.tokens import generate_raw_token, hash_token
from sqlalchemy import case, update
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _utc(value: datetime) -> datetime:
    """Normalize a possibly tz-naive datetime (e.g. read back from a
    SQLite test DB, which drops tzinfo) to UTC-aware for safe comparison."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


_DOWNLOAD_TOKEN_LIFETIME = timedelta(hours=24)
_UPLOAD_TOKEN_LIFETIME = timedelta(days=7)
_STATUS_TOKEN_LIFETIME = _UPLOAD_TOKEN_LIFETIME
_RUN_STAGE_ORDER = {
    "starting": 0,
    "training": 1,
    "sending_model": 2,
    "converting": 3,
    "sending_file": 4,
    "finished": 5,
}
RUN_STAGES = (*_RUN_STAGE_ORDER, "failed")
_MESSAGE_LIMIT = 500


@dataclass(frozen=True, slots=True)
class TrainingJobCreated:
    job: DpoTrainingJob
    raw_download_token: str
    raw_upload_token: str
    raw_status_token: str


def create_training_job(
    session: Session, agent_id: str, created_by: uuid.UUID
) -> TrainingJobCreated:
    """Create a training job: freeze the current DPO dataset for agent_id
    and mint a single-use download token plus a single-use upload token,
    both scoped to the new job."""
    validate_agent_id(agent_id)

    frozen = freeze_job_dataset(session, agent_id)
    pair_count = frozen.manifest_json.get("pair_count")
    if not isinstance(pair_count, int) or pair_count <= 0:
        raise EmptyTrainingDatasetError(
            f"no eligible DPO preference pairs exist for agent {agent_id!r}"
        )

    raw_download_token = generate_raw_token()
    raw_upload_token = generate_raw_token()
    raw_status_token = generate_raw_token()
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
        status_token_hash=hash_token(raw_status_token),
        status_expires_at=now + _STATUS_TOKEN_LIFETIME,
    )
    session.add(job)
    session.commit()

    return TrainingJobCreated(
        job=job,
        raw_download_token=raw_download_token,
        raw_upload_token=raw_upload_token,
        raw_status_token=raw_status_token,
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

    claim = session.execute(
        update(DpoTrainingJob)
        .where(
            DpoTrainingJob.job_id == job_id,
            DpoTrainingJob.download_token_hash == hash_token(raw_token),
            DpoTrainingJob.download_used_at.is_(None),
            DpoTrainingJob.download_expires_at >= now,
        )
        .values(
            download_used_at=now,
            status=case(
                (DpoTrainingJob.status == "completed", "completed"),
                else_="downloaded",
            ),
        )
        .execution_options(synchronize_session=False)
    )
    if claim.rowcount != 1:
        session.rollback()
        raise TrainingJobNotFoundError("invalid or expired download token")
    session.commit()

    return zip_bytes


def _apply_run_stage(
    job: DpoTrainingJob,
    stage: str,
    *,
    step: int | None,
    total: int | None,
    message: str | None,
    now: datetime,
) -> bool:
    """Apply a stage if it is allowed; return whether anything changed."""
    current = job.run_stage
    if current == "finished":
        return False
    if (
        stage != "failed"
        and current in _RUN_STAGE_ORDER
        and _RUN_STAGE_ORDER[stage] < _RUN_STAGE_ORDER[current]
    ):
        return False
    job.run_stage = stage
    job.run_step = step
    job.run_total = total
    job.run_message = message[:_MESSAGE_LIMIT] if message else None
    job.run_reported_at = now
    return True


def _verify_status_token(job: DpoTrainingJob, raw_token: str) -> bool:
    if not job.status_token_hash or job.status_expires_at is None:
        return False
    if _utc(job.status_expires_at) < datetime.now(UTC):
        return False
    return secrets.compare_digest(job.status_token_hash, hash_token(raw_token))


def report_run_status(
    session: Session,
    job_id: uuid.UUID,
    raw_token: str,
    stage: str,
    *,
    step: int | None = None,
    total: int | None = None,
    message: str | None = None,
) -> None:
    """Record a progress report from the notebook. Raises
    TrainingJobNotFoundError for any invalid-token condition (map to 404)."""
    job = session.get(DpoTrainingJob, job_id)
    if job is None or not _verify_status_token(job, raw_token):
        raise TrainingJobNotFoundError("invalid or expired status token")
    if _apply_run_stage(
        job, stage, step=step, total=total, message=message, now=datetime.now(UTC)
    ):
        session.commit()


def mark_run_stage(session: Session, job_id: uuid.UUID, stage: str) -> None:
    """Server-observed stage (adapter or GGUF stored). Never raises: a status
    problem must not turn a stored upload into an error."""
    try:
        job = session.get(DpoTrainingJob, job_id)
        if job is not None and _apply_run_stage(
            job,
            stage,
            step=None,
            total=None,
            message=None,
            now=datetime.now(UTC),
        ):
            session.commit()
    except Exception:
        logger.warning("could not record run stage %s", stage, exc_info=True)
        try:
            session.rollback()
        except Exception:
            logger.warning("rollback failed", exc_info=True)


def list_training_jobs(session: Session, agent_id: str) -> list[DpoTrainingJob]:
    return (
        session.query(DpoTrainingJob)
        .filter(DpoTrainingJob.agent_id == agent_id)
        .order_by(DpoTrainingJob.created_at.desc())
        .all()
    )


__all__ = [
    "RUN_STAGES",
    "VALID_AGENT_IDS",
    "TrainingJobCreated",
    "create_training_job",
    "get_job_download_package",
    "list_training_jobs",
    "mark_run_stage",
    "report_run_status",
]
