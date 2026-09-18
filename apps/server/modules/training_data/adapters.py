"""Training adapter upload lifecycle and registry queries."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import BinaryIO

from server.modules.training_data.adapter_artifacts import (
    discard_staged_adapter,
    publish_staged_adapter,
    remove_published_adapter,
    stage_adapter_artifact,
)
from server.modules.training_data.exceptions import TrainingJobNotFoundError
from server.modules.training_data.jobs import _utc
from server.modules.training_data.models import DpoTrainingJob, TrainedAdapter
from server.modules.training_data.tokens import hash_token
from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def _next_version(session: Session, agent_id: str) -> int:
    current_max = (
        session.query(func.max(TrainedAdapter.version))
        .filter(TrainedAdapter.agent_id == agent_id)
        .scalar()
    )
    return (current_max or 0) + 1


_MAX_VERSION_INSERT_RETRIES = 5


def store_adapter_upload(
    session: Session,
    job_id: uuid.UUID,
    raw_token: str,
    *,
    filename: str,
    source: BinaryIO,
) -> TrainedAdapter:
    """Validate, stage, atomically claim, publish, and register an adapter."""
    job = session.get(DpoTrainingJob, job_id)
    if job is None:
        raise TrainingJobNotFoundError("job not found")

    now = datetime.now(UTC)
    token_hash = hash_token(raw_token)
    if (
        job.upload_used_at is not None
        or _utc(job.upload_expires_at) < now
        or token_hash != job.upload_token_hash
    ):
        raise TrainingJobNotFoundError("invalid or expired upload token")

    adapter_id = uuid.uuid4()
    staged = stage_adapter_artifact(
        job.agent_id,
        adapter_id,
        filename=filename,
        source=source,
        expected_source_manifest=job.manifest_json,
    )
    published_path: str | None = None

    try:
        claim = session.execute(
            update(DpoTrainingJob)
            .where(
                DpoTrainingJob.job_id == job_id,
                DpoTrainingJob.upload_token_hash == token_hash,
                DpoTrainingJob.upload_used_at.is_(None),
                DpoTrainingJob.upload_expires_at >= now,
            )
            .values(upload_used_at=now, status="completed")
            .execution_options(synchronize_session=False)
        )
        if claim.rowcount != 1:
            session.rollback()
            raise TrainingJobNotFoundError("invalid or expired upload token")

        artifact = publish_staged_adapter(staged)
        published_path = artifact.file_path

        # Bounded retry loop for concurrent version allocation.
        # If another job for the same agent inserted an adapter concurrently,
        # IntegrityError on (agent_id, version) is caught and retried with the next
        # version. The upload token claim has already succeeded and must remain claimed.
        for attempt in range(_MAX_VERSION_INSERT_RETRIES):
            version = _next_version(session, job.agent_id)
            adapter = TrainedAdapter(
                adapter_id=artifact.adapter_id,
                agent_id=job.agent_id,
                job_id=job.job_id,
                version=version,
                file_path=artifact.file_path,
                file_sha256=artifact.file_sha256,
                size_bytes=artifact.size_bytes,
            )
            try:
                # Use a savepoint so an IntegrityError on the adapter row does not
                # rollback the enclosing transaction (which holds the token claim).
                with session.begin_nested():
                    session.add(adapter)
                    session.flush()
                break
            except IntegrityError:
                if attempt == _MAX_VERSION_INSERT_RETRIES - 1:
                    raise
                continue
        else:
            raise RuntimeError("failed to assign adapter version after max retries")
    except Exception:
        session.rollback()
        discard_staged_adapter(staged)
        if published_path is not None:
            remove_published_adapter(published_path)
        raise

    try:
        session.commit()
        return adapter
    except Exception:
        # Commit acknowledgement is ambiguous (e.g. transport disconnect).
        # The database transaction may have committed or will be rolled back.
        # Never delete a published artifact merely because commit ack is
        # ambiguous. Rollback the local session and re-raise.
        session.rollback()
        raise


def list_trained_adapters(session: Session, agent_id: str) -> list[TrainedAdapter]:
    return (
        session.query(TrainedAdapter)
        .filter(TrainedAdapter.agent_id == agent_id)
        .order_by(TrainedAdapter.version.desc())
        .all()
    )


__all__ = ["list_trained_adapters", "store_adapter_upload"]
