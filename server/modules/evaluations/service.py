"""
Evaluations business logic layer. Enforces job lifecycle, role/ownership, and
status transitions (including helpers for orchestrator use). Unauthorized
access is always 404 (masked) for non-owners.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from server.modules.documents import persistence
from server.modules.documents.curriculum.service import check_curriculum_readiness
from server.modules.documents.exceptions import DocumentNotFoundError
from server.modules.documents.models import Document
from server.modules.evaluations.exceptions import (
    EvaluationExecutionOwnershipError,
    EvaluationNotFoundError,
    EvaluationPipelineUnavailableError,
    InvalidEvaluationTargetError,
    InvalidStatusTransitionError,
)
from server.modules.evaluations.models import (
    EvaluationJob,
    EvaluationStatus,
    can_transition_status,
)
from server.modules.evaluations.schemas import (
    EvaluationListItem,
    EvaluationListResponse,
    EvaluationResponse,
    EvaluationStatusResponse,
    EvaluationSubmitRequest,
    LatestEvaluationItem,
    LatestEvaluationsResponse,
)
from sqlalchemy import func, inspect, or_, select, update
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


# Statuses considered terminal — once entered, no further transitions
# or token claims are allowed.
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


def create_evaluation(
    req: EvaluationSubmitRequest,
    submitted_by: uuid.UUID,
    db: Any = None,
    *,
    submitted_by_role: str | None = None,
    with_commit: bool = True,
) -> EvaluationResponse:
    if db is None:
        raise EvaluationPipelineUnavailableError(
            "Evaluation pipeline is not available yet."
        )

    # Validate SLM target (existence + source_type==slm + ownership) FIRST to
    # preserve security masking: missing, foreign SLM, or non-SLM returns
    # DocumentNotFoundError (404) before we reveal program or curriculum requirements.
    document = _validate_evaluation_target(
        req.document_id,
        submitted_by,
        db,
        expected_source_type="slm",
        user_role=submitted_by_role,
    )

    if not (req.confirmed_program and req.confirmed_program.strip()):
        raise InvalidEvaluationTargetError(
            "confirmed_program is required for evaluation submission."
        )

    confirmed_prog = req.confirmed_program.strip()
    if confirmed_prog not in ("BSCS", "BSInfoTech"):
        raise InvalidEvaluationTargetError(
            "Unsupported confirmed_program on write. Only BSCS and BSInfoTech "
            "are supported; BSIT is not accepted on submission."
        )

    if req.curriculum_id is not None and req.partial_without_curriculum:
        raise InvalidEvaluationTargetError(
            "Cannot specify curriculum_id when partial_without_curriculum is True."
        )

    if req.curriculum_id is None and not req.partial_without_curriculum:
        raise InvalidEvaluationTargetError(
            "curriculum_id is required when partial_without_curriculum is False."
        )

    curriculum_id: uuid.UUID | None = None
    partial_without_curriculum: bool
    partial_reason: str | None = None

    if req.curriculum_id is not None:
        readiness = check_curriculum_readiness(
            document=req.curriculum_id,
            program=confirmed_prog,
            db=db,
        )
        if not readiness.is_ready:
            logger.warning(
                "Curriculum readiness check failed during evaluation admission: "
                "curriculum_id=%s, program=%s, reason=%s",
                req.curriculum_id,
                confirmed_prog,
                readiness.reason,
            )
            raise InvalidEvaluationTargetError(
                "Curriculum is not ready for evaluation."
            )
        curriculum_id = readiness.document_id
        partial_without_curriculum = False
        partial_reason = None
    else:
        curriculum_id = None
        partial_without_curriculum = True
        partial_reason = (
            "Curriculum reference not provided; Coordinator review skipped."
        )

    syllabus = None
    if req.syllabus_id:
        syllabus = _validate_evaluation_target(
            req.syllabus_id,
            submitted_by,
            db,
            expected_source_type="syllabus",
        )

    job = EvaluationJob(
        evaluation_id=uuid.uuid4(),
        document_id=document.document_id,
        syllabus_id=syllabus.document_id if syllabus is not None else None,
        curriculum_id=curriculum_id,
        status=EvaluationStatus.SUBMITTED.value,
        error_message=None,
        partial_without_curriculum=partial_without_curriculum,
        partial_reason=partial_reason,
        confirmed_program=confirmed_prog,
        submitted_by=submitted_by,
        submitted_at=datetime.now(UTC),
        completed_at=None,
    )
    db.add(job)
    if with_commit:
        db.commit()

    return EvaluationResponse(
        evaluation_id=job.evaluation_id,
        document_id=job.document_id,
        syllabus_id=job.syllabus_id,
        curriculum_id=job.curriculum_id,
        status=EvaluationStatus(job.status),
        error_message=job.error_message,
        partial_without_curriculum=job.partial_without_curriculum,
        partial_reason=job.partial_reason,
        confirmed_program=job.confirmed_program,
        submitted_by=job.submitted_by,
        submitted_at=job.submitted_at,
        completed_at=job.completed_at,
        duration_seconds=_duration_seconds(job.submitted_at, job.completed_at),
    )


def _validate_evaluation_target(
    document_id: uuid.UUID,
    current_user_id: uuid.UUID,
    db: Any = None,
    *,
    expected_source_type: str,
    user_role: str | None = None,
) -> Document:
    if db is None:
        raise EvaluationPipelineUnavailableError(
            "Evaluation pipeline is not available yet."
        )

    from server.modules.auth.models import UserRole
    from server.modules.documents.schemas import REFERENCE_SOURCE_TYPES

    document = db.get(Document, document_id)
    if document is None:
        raise DocumentNotFoundError(f"Document {document_id} not found")

    # Admins bypass the SLM ownership check so they can create
    # benchmark evaluations on faculty-uploaded SLM documents.
    is_admin = user_role == UserRole.ADMIN.value if user_role else False

    # For evaluation primary target (slm), combine existence, source_type == 'slm',
    # and ownership into the same masked DocumentNotFoundError (404).
    if expected_source_type == "slm":
        if document.source_type != "slm":
            raise DocumentNotFoundError(f"Document {document_id} not found")
        if not is_admin and document.uploaded_by != current_user_id:
            raise DocumentNotFoundError(f"Document {document_id} not found")
    else:
        # Non-SLM targets (e.g. syllabus)
        if not is_admin:
            if expected_source_type in REFERENCE_SOURCE_TYPES:
                # References are shared; skip ownership check
                pass
            elif document.uploaded_by != current_user_id:
                raise DocumentNotFoundError(f"Document {document_id} not found")

        if document.source_type != expected_source_type:
            raise InvalidEvaluationTargetError(
                f"Document must have source_type={expected_source_type}."
            )

    if document.processing_status != "PROCESSED":
        raise InvalidEvaluationTargetError(
            "Document must be fully processed before evaluation."
        )

    chunks = persistence.get_document_chunks(document_id, db=db)
    if not chunks:
        raise InvalidEvaluationTargetError(
            "Document must have chunks before evaluation submission."
        )

    if document.source_type != "slm" and not all(
        getattr(chunk, "chroma_stored", False) for chunk in chunks
    ):
        raise InvalidEvaluationTargetError(
            "Document must have Chroma-ready chunks before evaluation submission."
        )

    return document


def _check_ownership_or_404(
    row: EvaluationJob, current_user_id: uuid.UUID, current_user_role: str
):
    if row.submitted_by != current_user_id:
        # Always mask existence as 404 if not the owner.
        raise EvaluationNotFoundError("Not found.")


def get_evaluation(
    evaluation_id: uuid.UUID,
    current_user_id: uuid.UUID,
    current_user_role: str,
    db: Any = None,
) -> EvaluationResponse:
    row = db.get(EvaluationJob, evaluation_id) if db is not None else None
    if row is None:
        raise EvaluationNotFoundError(f"Evaluation {evaluation_id} not found")
    _check_ownership_or_404(row, current_user_id, current_user_role)
    return EvaluationResponse(
        evaluation_id=row.evaluation_id,
        document_id=row.document_id,
        syllabus_id=row.syllabus_id,
        curriculum_id=row.curriculum_id,
        status=EvaluationStatus(row.status),
        error_message=row.error_message,
        partial_without_curriculum=row.partial_without_curriculum,
        partial_reason=row.partial_reason,
        confirmed_program=row.confirmed_program,
        submitted_by=row.submitted_by,
        submitted_at=row.submitted_at,
        completed_at=row.completed_at,
        duration_seconds=_duration_seconds(row.submitted_at, row.completed_at),
    )


def list_evaluations(
    page: int,
    page_size: int,
    current_user_id: uuid.UUID,
    current_user_role: str,
    db: Any = None,
    *,
    document_id: uuid.UUID | None = None,
) -> EvaluationListResponse:
    if db is not None:
        query = db.query(EvaluationJob)
        query = query.filter(EvaluationJob.submitted_by == current_user_id)
        if document_id is not None:
            query = query.filter(EvaluationJob.document_id == document_id)
        total = query.count()
        rows = (
            query.order_by(EvaluationJob.submitted_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        doc_ids = [row.document_id for row in rows]
        doc_titles = {
            d.document_id: d.title
            for d in db.query(Document).filter(Document.document_id.in_(doc_ids)).all()
        }
        items = [
            EvaluationListItem(
                evaluation_id=row.evaluation_id,
                document_id=row.document_id,
                document_title=doc_titles.get(row.document_id),
                syllabus_id=row.syllabus_id,
                curriculum_id=row.curriculum_id,
                status=EvaluationStatus(row.status),
                partial_without_curriculum=row.partial_without_curriculum,
                partial_reason=row.partial_reason,
                confirmed_program=row.confirmed_program,
                submitted_at=row.submitted_at,
                completed_at=row.completed_at,
                duration_seconds=_duration_seconds(row.submitted_at, row.completed_at),
            )
            for row in rows
        ]
        return EvaluationListResponse(
            items=items, total=total, page=page, page_size=page_size
        )
    return EvaluationListResponse(items=[], total=0, page=page, page_size=page_size)


def get_evaluation_status(
    evaluation_id: uuid.UUID,
    current_user_id: uuid.UUID,
    current_user_role: str,
    db: Any = None,
) -> EvaluationStatusResponse:
    row = db.get(EvaluationJob, evaluation_id) if db is not None else None
    if row is None:
        raise EvaluationNotFoundError(f"Evaluation {evaluation_id} not found")
    _check_ownership_or_404(row, current_user_id, current_user_role)
    return EvaluationStatusResponse(
        evaluation_id=row.evaluation_id,
        status=EvaluationStatus(row.status),
        error_message=row.error_message,
        partial_without_curriculum=row.partial_without_curriculum,
        partial_reason=row.partial_reason,
        completed_at=row.completed_at,
        duration_seconds=_duration_seconds(row.submitted_at, row.completed_at),
    )


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


def get_latest_evaluations(
    document_ids: list[uuid.UUID],
    current_user_id: uuid.UUID,
    db: Any = None,
) -> LatestEvaluationsResponse:
    if not document_ids or db is None:
        return LatestEvaluationsResponse(items=[])

    rn_col = (
        func.row_number()
        .over(
            partition_by=EvaluationJob.document_id,
            order_by=(
                EvaluationJob.submitted_at.desc(),
                EvaluationJob.evaluation_id.desc(),
            ),
        )
        .label("rn")
    )

    subquery = (
        select(
            EvaluationJob.document_id,
            EvaluationJob.evaluation_id,
            EvaluationJob.status,
            EvaluationJob.submitted_at,
            EvaluationJob.completed_at,
            EvaluationJob.error_message,
            rn_col,
        )
        .where(
            EvaluationJob.submitted_by == current_user_id,
            EvaluationJob.document_id.in_(document_ids),
        )
        .subquery()
    )

    stmt = select(
        subquery.c.document_id,
        subquery.c.evaluation_id,
        subquery.c.status,
        subquery.c.submitted_at,
        subquery.c.completed_at,
        subquery.c.error_message,
    ).where(subquery.c.rn == 1)

    rows = db.execute(stmt).all()

    items = [
        LatestEvaluationItem(
            document_id=row.document_id,
            evaluation_id=row.evaluation_id,
            status=EvaluationStatus(row.status),
            submitted_at=row.submitted_at,
            completed_at=row.completed_at,
            error_message=row.error_message,
        )
        for row in rows
    ]
    return LatestEvaluationsResponse(items=items)


def admission_schema_ready(db: Any) -> bool:
    """Verify the complete admission lease contract without mutating schema."""
    try:
        bind = db.get_bind()
        inspector = inspect(bind)
        columns = {c["name"] for c in inspector.get_columns("evaluation_jobs")}
        required_columns = {
            "admission_slot",
            "execution_token",
            "execution_started_at",
            "execution_heartbeat_at",
        }
        if not required_columns.issubset(columns):
            return False
        checks = {
            c.get("name") for c in inspector.get_check_constraints("evaluation_jobs")
        }
        uniques = {
            c.get("name") for c in inspector.get_unique_constraints("evaluation_jobs")
        }
        indexes = {i.get("name") for i in inspector.get_indexes("evaluation_jobs")}
        return (
            "ck_evaluation_admission_slot" in checks
            and "uq_evaluation_admission_slot" in uniques
            and "idx_jobs_admission_fifo" in indexes
        )
    except Exception:
        db.rollback()
        return False


__all__ = [
    "create_evaluation",
    "get_evaluation",
    "list_evaluations",
    "get_latest_evaluations",
    "get_evaluation_status",
    "transition_evaluation_status",
    "acquire_evaluation_execution",
    "acquire_next_evaluation_execution",
    "heartbeat_evaluation_execution",
    "recover_stale_evaluation_execution",
    "seconds_until_stale_evaluation_execution",
    "admission_schema_ready",
    "_validate_evaluation_target",
]
