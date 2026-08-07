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
    Index,
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
        Index("idx_curriculum_map_cells_course_id", "course_id"),
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


class ProgramRoadmap(Base):
    """A versioned, per-program career roadmap (e.g. BSCS Intelligent
    Systems). Structured program-structure data for agent reference --
    seeded from JSON like the curriculum map, never embedded into Chroma.

    At most one version is ``active`` per (program, specialization) pair;
    the seed script enforces that by retiring superseded versions, and
    resolution always picks the highest version among ``active`` rows.
    """

    __tablename__ = "program_roadmaps"
    __table_args__ = (
        UniqueConstraint(
            "program",
            "specialization",
            "version_number",
            name="uq_program_roadmaps_program_specialization_version",
        ),
        CheckConstraint(
            "status IN ('active', 'retired')", name="ck_program_roadmaps_status"
        ),
    )

    roadmap_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    program: Mapped[str] = mapped_column(String(50), nullable=False)
    specialization: Mapped[str | None] = mapped_column(String(200), nullable=True)
    version_number: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    source_document_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RoadmapYear(Base):
    """One year-level (optionally semester-level) block within a roadmap."""

    __tablename__ = "roadmap_years"
    __table_args__ = (
        UniqueConstraint(
            "roadmap_id", "year_number", "semester", name="uq_roadmap_years_position"
        ),
        Index("idx_roadmap_years_roadmap_id", "roadmap_id"),
    )

    year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    roadmap_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("program_roadmaps.roadmap_id"), nullable=False
    )
    year_number: Mapped[int] = mapped_column(nullable=False)
    semester: Mapped[int | None] = mapped_column(nullable=True)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class RoadmapCourse(Base):
    """One course row within a roadmap year, enriched with roadmap-specific
    metadata (tech stack, competency stage). ``course_status`` marks courses
    that do not officially exist yet (``proposed``); proposed courses are
    informational only and never anchor alignment scoring. ``course_id`` is a
    nullable co-reference to the canonical ``courses`` table -- null for
    proposed courses, resolved by ``course_code`` when null.
    """

    __tablename__ = "roadmap_courses"
    __table_args__ = (
        CheckConstraint(
            "course_status IN ('existing', 'proposed')",
            name="ck_roadmap_courses_course_status",
        ),
        UniqueConstraint(
            "roadmap_id", "course_code", name="uq_roadmap_courses_roadmap_code"
        ),
        Index("idx_roadmap_courses_year_id", "year_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    roadmap_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("program_roadmaps.roadmap_id"), nullable=False
    )
    year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("roadmap_years.year_id"), nullable=False
    )
    course_code: Mapped[str] = mapped_column(String(50), nullable=False)
    course_title: Mapped[str] = mapped_column(String(300), nullable=False)
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("courses.course_id"), nullable=True
    )
    course_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="existing"
    )
    tech_stack: Mapped[str | None] = mapped_column(Text, nullable=True)
    competency_stage: Mapped[str | None] = mapped_column(String(100), nullable=True)
    learning_outcomes_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    portfolio_project_suggestion: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    relevant_certification: Mapped[str | None] = mapped_column(
        String(300), nullable=True
    )


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


__all__ = [
    "Course",
    "CurriculumObjective",
    "CurriculumMapCell",
    "ProgramRoadmap",
    "RoadmapYear",
    "RoadmapCourse",
    "CurriculumAlignmentCheck",
]
