"""SQLAlchemy models for the curriculum alignment pipeline.

Structured tabular data (exact I/E/D cells), stored relationally like the
``rubrics`` module -- not embedded/retrieved from Chroma. A blank mapping
cell is the absence of a row in ``curriculum_map_cells``, not a stored null.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from server.core.database import Base
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (UniqueConstraint("course_code", name="uq_courses_course_code"),)

    course_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    course_code: Mapped[str] = mapped_column(String(50), nullable=False)
    course_title: Mapped[str] = mapped_column(String(300), nullable=False)
    program: Mapped[str] = mapped_column(String(50), nullable=False)


class CurriculumObjective(Base):
    __tablename__ = "curriculum_objectives"
    __table_args__ = (
        UniqueConstraint(
            "code", "program", name="uq_curriculum_objectives_code_program"
        ),
    )

    objective_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    program: Mapped[str] = mapped_column(String(50), nullable=False)


class CurriculumMapCell(Base):
    __tablename__ = "curriculum_map_cells"
    __table_args__ = (
        UniqueConstraint(
            "course_id", "objective_id", name="uq_curriculum_map_cells_course_objective"
        ),
        CheckConstraint(
            "level IN ('I', 'E', 'D')", name="ck_curriculum_map_cells_level"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("courses.course_id"), nullable=False
    )
    objective_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("curriculum_objectives.objective_id"),
        nullable=False,
    )
    level: Mapped[str] = mapped_column(String(1), nullable=False)


class CurriculumAlignmentCheck(Base):
    __tablename__ = "curriculum_alignment_checks"

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
    objective_results: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False
    )
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


__all__ = [
    "Course",
    "CurriculumObjective",
    "CurriculumMapCell",
    "CurriculumAlignmentCheck",
]
