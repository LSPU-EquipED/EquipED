"""Catalog and roadmap queries for curriculum maps."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func

from .exceptions import RoadmapNotFoundError
from .models import (
    Course,
    CurriculumMapCell,
    CurriculumObjective,
    ProgramRoadmap,
    RoadmapCourse,
    RoadmapYear,
)

_CANONICAL_PROGRAM = "BSInfoTech"
_PROGRAM_ALIASES = ("BSINFOTECH", "BSIT")

def normalize_program(program: str | None) -> str | None:
    if program is None:
        return None
    normalized = program.strip().upper()
    return _CANONICAL_PROGRAM if normalized in _PROGRAM_ALIASES else normalized


def list_courses(db: Any) -> list[Course]:
    return db.query(Course).order_by(Course.course_code).all()


def list_roadmaps(db: Any) -> list[ProgramRoadmap]:
    """All program roadmaps, ordered by program, specialization, then version
    (newest first within a pair)."""
    return (
        db.query(ProgramRoadmap)
        .order_by(
            ProgramRoadmap.program,
            ProgramRoadmap.specialization,
            ProgramRoadmap.version_number.desc(),
        )
        .all()
    )


def get_roadmap(roadmap_id: uuid.UUID, db: Any) -> ProgramRoadmap:
    roadmap = db.get(ProgramRoadmap, roadmap_id)
    if roadmap is None:
        raise RoadmapNotFoundError(f"Roadmap {roadmap_id} not found")
    return roadmap


def get_roadmap_detail(
    roadmap_id: uuid.UUID, db: Any
) -> tuple[ProgramRoadmap, list[dict[str, Any]]]:
    """Return the roadmap plus its years (ordered by year_number, semester
    nulls first), each year carrying its courses ordered by course_code."""
    roadmap = get_roadmap(roadmap_id, db)
    years = (
        db.query(RoadmapYear)
        .filter(RoadmapYear.roadmap_id == roadmap_id)
        .order_by(
            RoadmapYear.year_number,
            RoadmapYear.semester.is_(None),
            RoadmapYear.semester,
        )
        .all()
    )
    result: list[dict[str, Any]] = []
    for year in years:
        courses = (
            db.query(RoadmapCourse)
            .filter(RoadmapCourse.year_id == year.year_id)
            .order_by(RoadmapCourse.course_code)
            .all()
        )
        result.append(
            {
                "year_id": year.year_id,
                "year_number": year.year_number,
                "semester": year.semester,
                "label": year.label,
                "description": year.description,
                "courses": courses,
            }
        )
    return roadmap, result


def list_roadmap_courses(
    roadmap_id: uuid.UUID, year_number: int, semester: int | None, db: Any
) -> list[RoadmapCourse]:
    """Courses of one roadmap for a given year. When ``semester`` is None all
    semesters of the year are included; otherwise only that semester. Raises
    ``RoadmapNotFoundError`` when the roadmap is missing."""
    get_roadmap(roadmap_id, db)
    query = (
        db.query(RoadmapCourse)
        .join(RoadmapYear, RoadmapCourse.year_id == RoadmapYear.year_id)
        .filter(
            RoadmapCourse.roadmap_id == roadmap_id,
            RoadmapYear.year_number == year_number,
        )
    )
    if semester is not None:
        query = query.filter(RoadmapYear.semester == semester)
    return (
        query.order_by(
            RoadmapYear.year_number,
            RoadmapYear.semester.is_(None),
            RoadmapYear.semester,
            RoadmapCourse.course_code,
        )
        .all()
    )


def resolve_roadmap_course_context(
    *, program: str | None, course_code: str | None, db: Any
) -> dict[str, Any] | None:
    """Resolve a course's roadmap context for agent reference.

    Returns None when program/course_code is missing or empty, when no
    ``active`` roadmap exists for the program, when no course row matches the
    code (case-insensitive), or when the matched course is ``proposed``.
    Never raises. Program is normalized (``BSIT`` -> ``BSInfoTech``, case-
    insensitive) then matched case-insensitively against ``roadmap.program``;
    when multiple active roadmaps exist (shouldn't), the highest version wins.
    """
    if not program or not course_code:
        return None
    canonical = normalize_program(program)
    if canonical is None:
        return None

    roadmap = (
        db.query(ProgramRoadmap)
        .filter(
            func.lower(ProgramRoadmap.program) == canonical.lower(),
            ProgramRoadmap.status == "active",
        )
        .order_by(ProgramRoadmap.version_number.desc())
        .limit(1)
        .first()
    )
    if roadmap is None:
        return None

    course = (
        db.query(RoadmapCourse)
        .filter(
            RoadmapCourse.roadmap_id == roadmap.roadmap_id,
            func.lower(RoadmapCourse.course_code) == course_code.strip().lower(),
        )
        .order_by(RoadmapCourse.id)
        .first()
    )
    if course is None or course.course_status == "proposed":
        return None

    year = db.get(RoadmapYear, course.year_id)
    if year is None:
        return None
    return {
        "course_code": course.course_code,
        "course_title": course.course_title,
        "year": year.year_number,
        "semester": year.semester,
        "tech_stack": course.tech_stack,
        "competency_stage": course.competency_stage,
        "course_status": course.course_status,
    }



def get_course(course_id: uuid.UUID, db: Any) -> Course | None:
    course = db.get(Course, course_id)
    if course is None:
        return None
    return course


def get_mapped_objectives(course_id: uuid.UUID, db: Any) -> list[dict[str, Any]]:
    """Rows for this course only -- blank cells are absent rows, so this
    query already excludes them by construction (design spec section 3).
    """
    rows = (
        db.query(CurriculumMapCell, CurriculumObjective)
        .join(
            CurriculumObjective,
            CurriculumMapCell.objective_id == CurriculumObjective.objective_id,
        )
        .filter(CurriculumMapCell.course_id == course_id)
        .all()
    )
    return [
        {
            "code": objective.code,
            "description": objective.description,
            "expected_level": cell.level,
            "program": objective.program,
        }
        for cell, objective in rows
    ]


__all__ = [
    "normalize_program", "get_course", "get_mapped_objectives", "list_courses",
    "list_roadmaps", "get_roadmap", "get_roadmap_detail", "list_roadmap_courses",
    "resolve_roadmap_course_context",
]
