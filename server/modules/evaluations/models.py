"""SQLAlchemy models for evaluation job lifecycle state."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

import sqlalchemy as sa
from server.core.database import Base
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column


class EvaluationStatus(StrEnum):
    """Known lifecycle states for an evaluation job."""

    SUBMITTED = "SUBMITTED"
    PREPROCESSING = "PREPROCESSING"
    EVALUATING = "EVALUATING"
    SYNTHESIZING = "SYNTHESIZING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


ALLOWED_STATUS_TRANSITIONS: dict[EvaluationStatus, tuple[EvaluationStatus, ...]] = {
    EvaluationStatus.SUBMITTED: (
        EvaluationStatus.PREPROCESSING,
        EvaluationStatus.FAILED,
    ),
    EvaluationStatus.PREPROCESSING: (
        EvaluationStatus.EVALUATING,
        EvaluationStatus.FAILED,
    ),
    EvaluationStatus.EVALUATING: (
        EvaluationStatus.SYNTHESIZING,
        EvaluationStatus.FAILED,
    ),
    EvaluationStatus.SYNTHESIZING: (
        EvaluationStatus.COMPLETED,
        EvaluationStatus.FAILED,
    ),
    EvaluationStatus.COMPLETED: (),
    EvaluationStatus.FAILED: (),
}


class EvaluationJob(Base):
    """Persisted tracking row for a single evaluation request."""

    __tablename__ = "evaluation_jobs"
    __table_args__ = (
        Index("idx_jobs_document_id", "document_id"),
        Index("idx_jobs_status", "status"),
    )

    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.document_id"),
        nullable=False,
    )
    syllabus_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.document_id"),
        nullable=True,
    )
    curriculum_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.document_id"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=EvaluationStatus.SUBMITTED.value
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.user_id"), nullable=True
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Internal execution ownership fields used by the Phase 1 sequential
    # BackgroundTasks runner. These are NOT exposed via the public API.
    # `execution_token` is set when a runner claims a non-terminal job; it
    # is cleared by terminal transitions or by the startup recovery helper.
    execution_token: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    execution_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    execution_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    partial_without_curriculum: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False
    )
    partial_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed_program: Mapped[str | None] = mapped_column(String(50), nullable=True)


def can_transition_status(
    current: EvaluationStatus | str, next_status: EvaluationStatus | str
) -> bool:
    """Return whether a lifecycle move is allowed."""

    current_status = EvaluationStatus(current)
    target_status = EvaluationStatus(next_status)
    return target_status in ALLOWED_STATUS_TRANSITIONS[current_status]


__all__ = [
    "ALLOWED_STATUS_TRANSITIONS",
    "EvaluationJob",
    "EvaluationStatus",
    "can_transition_status",
]
