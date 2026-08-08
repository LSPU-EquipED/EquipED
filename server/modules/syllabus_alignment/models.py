"""SQLAlchemy models for standalone syllabus alignment runs."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

import sqlalchemy as sa
from server.core.database import Base
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column


class SyllabusAlignmentStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class SyllabusAlignmentLevel(StrEnum):
    MEETS = "MEETS"
    PARTIALLY_MEETS = "PARTIALLY_MEETS"
    DOES_NOT_MEET = "DOES_NOT_MEET"
    UNAVAILABLE = "UNAVAILABLE"


class SyllabusAlignmentRun(Base):
    """A standalone, owner-scoped SLM-to-syllabus advisory run."""

    __tablename__ = "syllabus_alignment_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('QUEUED', 'RUNNING', 'COMPLETED', 'FAILED')",
            name="ck_syllabus_alignment_status",
        ),
        CheckConstraint(
            "(status IN ('QUEUED', 'RUNNING') AND alignment_level IS NULL) OR "
            "(status = 'COMPLETED' AND alignment_level IN "
            "('MEETS', 'PARTIALLY_MEETS', 'DOES_NOT_MEET')) OR "
            "(status = 'FAILED' AND alignment_level = 'UNAVAILABLE')",
            name="ck_syllabus_alignment_level_for_status",
        ),
        Index("idx_syllabus_alignment_owner_created", "requested_by", "created_at"),
        Index("idx_syllabus_alignment_slm_created", "slm_document_id", "created_at"),
        Index("idx_syllabus_alignment_syllabus", "syllabus_document_id"),
        Index("uq_syllabus_alignment_slm", "slm_document_id", unique=True),
    )
    alignment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slm_document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.document_id"), nullable=False
    )
    syllabus_document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.document_id"), nullable=False
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.user_id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SyllabusAlignmentStatus.QUEUED.value
    )
    alignment_level: Mapped[str | None] = mapped_column(String(30), nullable=True)
    justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    alignment_artifact: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    provenance: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


__all__ = ["SyllabusAlignmentLevel", "SyllabusAlignmentRun", "SyllabusAlignmentStatus"]
