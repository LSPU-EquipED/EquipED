"""SQLAlchemy models for curriculum alignment."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from server.core.database import Base
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column


class CurriculumAlignmentCheck(Base):
    __tablename__ = "curriculum_alignment_checks"
    __table_args__ = (
        Index(
            "idx_curriculum_alignment_checks_document_run_at",
            "document_id",
            "run_at",
        ),
        Index("idx_curriculum_alignment_checks_course_id", "course_id"),
    )
    check_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.document_id"), nullable=False
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("courses.course_id"), nullable=False
    )
    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provenance: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    objective_results: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False
    )
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

__all__ = ["CurriculumAlignmentCheck"]
