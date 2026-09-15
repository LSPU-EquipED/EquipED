"""Evaluation execution queue: CAS tokens, heartbeats, and stale lease recovery."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from server.modules.evaluations.exceptions import (
    EvaluationExecutionOwnershipError,
    EvaluationNotFoundError,
    InvalidStatusTransitionError,
)
from server.modules.evaluations.models import (
    EvaluationJob,
    EvaluationStatus,
    can_transition_status,
)
from server.modules.evaluations.schemas import EvaluationStatusResponse
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

_TERMINAL_STATUSES: tuple[str, ...] = (
    EvaluationStatus.COMPLETED.value,
    EvaluationStatus.FAILED.value,
)


def _duration_seconds(
    submitted_at: datetime | None,
    completed_at: datetime | None,
) -> float | None:
    if completed_at is not None and submitted_at is not None:
        return (completed_at - submitted_at).total_seconds()
    return None


def transition_evaluation_status(
    evaluation_id: uuid.UUID,
    new_status: EvaluationStatus,
    db: Any,
    *,
    error_message: str | None = None,
    execution_token: uuid.UUID | None = None,
    expected_status: EvaluationStatus | None = None,
    commit: bool = True,
) -> EvaluationStatusResponse:
    row = db.get(EvaluationJob, evaluation_id) if db is not None else None
    if row is None:
        raise EvaluationNotFoundError(f"Evaluation {evaluation_id} not found")
    if row.status in _TERMINAL_STATUSES:
        # No transitions out of terminal state
        return EvaluationStatusResponse(
            evaluation_id=row.evaluation_id,
            status=EvaluationStatus(row.status),
            error_message=row.error_message,
            target_agent=getattr(row, "target_agent", "all") or "all",
            partial_without_curriculum=row.partial_without_curriculum,
            partial_reason=row.partial_reason,
            completed_at=row.completed_at,
            duration_seconds=_duration_seconds(row.submitted_at, row.completed_at),
        )
    # Same-state non-terminal transition: idempotent no-op. Validate
    # token ownership when one is supplied, but do NOT clear/replace
    # the token or alter timestamps/status.
    if row.status == new_status.value:
        if execution_token is not None and row.execution_token != execution_token:
            raise EvaluationExecutionOwnershipError(
                f"Execution token mismatch for evaluation {evaluation_id}"
            )
        return EvaluationStatusResponse(
            evaluation_id=row.evaluation_id,
            status=EvaluationStatus(row.status),
            error_message=row.error_message,
            target_agent=getattr(row, "target_agent", "all") or "all",
            partial_without_curriculum=row.partial_without_curriculum,
            partial_reason=row.partial_reason,
            completed_at=row.completed_at,
            duration_seconds=_duration_seconds(row.submitted_at, row.completed_at),
        )
    if not can_transition_status(row.status, new_status):
        raise InvalidStatusTransitionError(f"Cannot move {row.status} -> {new_status}")
    if execution_token is not None and row.execution_token != execution_token:
        # Token was provided but does not match the current row ownership.
        # This guards against stale runners mutating state they no longer own.
        raise EvaluationExecutionOwnershipError(
            f"Execution token mismatch for evaluation {evaluation_id}"
        )
    values: dict[str, Any] = {"status": new_status.value}
    if error_message is not None:
        values["error_message"] = error_message
    if new_status in [EvaluationStatus.COMPLETED, EvaluationStatus.FAILED]:
        values.update(
            completed_at=datetime.now(UTC),
            admission_slot=None,
            execution_token=None,
            execution_started_at=None,
            execution_heartbeat_at=None,
        )
    predicate = [
        EvaluationJob.evaluation_id == evaluation_id,
        EvaluationJob.status
        == (expected_status.value if expected_status else row.status),
    ]
    if execution_token is not None:
        predicate.append(EvaluationJob.execution_token == execution_token)
    result = db.execute(update(EvaluationJob).where(*predicate).values(**values))
    if result.rowcount != 1:
        db.rollback()
        raise EvaluationExecutionOwnershipError("Evaluation status ownership changed")
    if commit:
        db.commit()
        db.refresh(row)
    return EvaluationStatusResponse(
        evaluation_id=row.evaluation_id,
        status=EvaluationStatus(row.status),
        error_message=row.error_message,
        target_agent=getattr(row, "target_agent", "all") or "all",
        partial_without_curriculum=row.partial_without_curriculum,
        partial_reason=row.partial_reason,
        completed_at=row.completed_at,
        duration_seconds=_duration_seconds(row.submitted_at, row.completed_at),
    )


def acquire_evaluation_execution(
    db: Any,
    evaluation_id: uuid.UUID,
    execution_token: uuid.UUID,
) -> bool:
    """Atomically claim an evaluation job for execution.

    Returns True if the caller now owns the job, False if the job is
    missing, already terminal, or already claimed by another runner.

    Uses a single conditional UPDATE so concurrent runners cannot both
    succeed (the rowcount is 1 for exactly one claim).
    """

    now = datetime.now(UTC)
    result = db.execute(
        update(EvaluationJob)
        .where(
            EvaluationJob.evaluation_id == evaluation_id,
            EvaluationJob.execution_token.is_(None),
            EvaluationJob.admission_slot.is_(None),
            EvaluationJob.status == EvaluationStatus.SUBMITTED.value,
        )
        .values(
            status=EvaluationStatus.PREPROCESSING.value,
            admission_slot=1,
            execution_token=execution_token,
            execution_started_at=now,
            execution_heartbeat_at=now,
        )
    )
    db.commit()
    return result.rowcount == 1


def acquire_next_evaluation_execution(
    db: Any, execution_token: uuid.UUID
) -> uuid.UUID | None:
    """Claim the oldest submitted job for the sole admission slot."""
    query = (
        select(EvaluationJob.evaluation_id)
        .where(
            EvaluationJob.status == EvaluationStatus.SUBMITTED.value,
            EvaluationJob.execution_token.is_(None),
            EvaluationJob.admission_slot.is_(None),
        )
        .order_by(EvaluationJob.submitted_at, EvaluationJob.evaluation_id)
        .limit(1)
    )
    if db.get_bind().dialect.name == "postgresql":
        # Deliberately wait on the oldest row.  SKIP LOCKED would violate FIFO
        # by allowing a newer request to leapfrog a claimant holding the slot.
        query = query.with_for_update()
    candidate = db.execute(query).scalar_one_or_none()
    if candidate is None:
        return None
    try:
        return (
            candidate
            if acquire_evaluation_execution(db, candidate, execution_token)
            else None
        )
    except IntegrityError:
        # SQLite lacks PostgreSQL's row-lock/skip-locked semantics; a concurrent
        # loser may surface the slot unique constraint instead of rowcount=0.
        db.rollback()
        return None


def heartbeat_evaluation_execution(
    db: Any,
    evaluation_id: uuid.UUID,
    execution_token: uuid.UUID,
) -> bool:
    """Refresh the heartbeat timestamp for an owned evaluation job.

    Returns True if the heartbeat was updated, False if the token no
    longer matches (the caller has lost ownership).
    """

    now = datetime.now(UTC)
    result = db.execute(
        update(EvaluationJob)
        .where(
            EvaluationJob.evaluation_id == evaluation_id,
            EvaluationJob.execution_token == execution_token,
            EvaluationJob.admission_slot == 1,
        )
        .values(execution_heartbeat_at=now)
    )
    db.commit()
    return result.rowcount == 1


def recover_stale_evaluation_execution(
    db: Any, stale_before: datetime
) -> tuple[tuple[uuid.UUID, ...], int]:
    """Atomically requeue stale, nonterminal jobs and return their IDs/count."""
    result = db.execute(
        update(EvaluationJob)
        .where(
            EvaluationJob.status.in_(
                (
                    EvaluationStatus.PREPROCESSING.value,
                    EvaluationStatus.EVALUATING.value,
                    EvaluationStatus.SYNTHESIZING.value,
                )
            ),
            or_(
                EvaluationJob.execution_token.is_(None),
                EvaluationJob.execution_heartbeat_at.is_(None),
                EvaluationJob.execution_heartbeat_at < stale_before,
            ),
        )
        .values(
            admission_slot=None,
            execution_token=None,
            execution_started_at=None,
            execution_heartbeat_at=None,
            status=EvaluationStatus.SUBMITTED.value,
            completed_at=None,
            error_message=None,
        )
        .returning(EvaluationJob.evaluation_id)
    )
    recovered_ids = tuple(result.scalars().all())
    db.commit()
    return recovered_ids, len(recovered_ids)


def seconds_until_stale_evaluation_execution(
    db: Any, stale_seconds: float
) -> float | None:
    """Return seconds until the earliest active lease becomes recoverable."""
    heartbeats = (
        db.execute(
            select(EvaluationJob.execution_heartbeat_at).where(
                EvaluationJob.admission_slot == 1,
                EvaluationJob.status.in_(
                    (
                        EvaluationStatus.PREPROCESSING.value,
                        EvaluationStatus.EVALUATING.value,
                        EvaluationStatus.SYNTHESIZING.value,
                    )
                ),
            )
        )
        .scalars()
        .all()
    )
    if not heartbeats:
        return None
    now = datetime.now(UTC)

    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    return max(
        0.0,
        min(
            (
                _as_utc(heartbeat) + timedelta(seconds=stale_seconds) - now
            ).total_seconds()
            if heartbeat is not None
            else 0.0
            for heartbeat in heartbeats
        ),
    )


__all__ = [
    "_TERMINAL_STATUSES",
    "acquire_evaluation_execution",
    "acquire_next_evaluation_execution",
    "heartbeat_evaluation_execution",
    "recover_stale_evaluation_execution",
    "seconds_until_stale_evaluation_execution",
    "transition_evaluation_status",
]
