"""Idempotent, convergent seed script for versioned program roadmaps (e.g.
BSCS Intelligent Systems). Mirrors server/scripts/seed_curriculum_map.py's
shape (module-style, sys.path insertion, commit-once).

Convergence rules (safe for repeat runs):
- The roadmap row for ``(program, specialization, version_number)`` is
  upserted and its status/source_document_path corrected in place.
- At most one version is ``active`` per (program, specialization) pair:
  seeding enforces that by retiring any other ``active`` roadmap for the same
  pair.
- Years and courses defined by the seed JSON are upserted; labels, course
  metadata, and statuses are corrected in place.
- Convergence is roadmap-scoped: courses whose code is no longer in the
  payload, and years no longer present in the payload, are removed. No other
  roadmap's rows are ever touched.

Usage (from repo root):
    uv run --project server python -m server.scripts.seed_roadmaps
    uv run --project server python -m server.scripts.seed_roadmaps --input <path>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import func  # noqa: E402

from server.modules.curriculum.models import (  # noqa: E402
    Course,
    ProgramRoadmap,
    RoadmapCourse,
    RoadmapYear,
)

#: Allowed course_status values in the seed payload.
_VALID_COURSE_STATUSES = ("existing", "proposed")
#: Canonical program pair treated as equivalent when co-referencing courses.
_PROGRAM_ALIASES = ("BSInfoTech", "BSIT")


def _canonical_program(value: str) -> str:
    """Canonical-case a program: strip + upper, mapping the legacy ``BSIT``
    alias onto ``BSInfoTech``. Mirrors the service's ``_normalize_program`` so
    the stored ``roadmap.program`` is always canonical-case and co-reference
    matching is case-insensitive."""
    normalized = str(value).strip().upper()
    return "BSInfoTech" if normalized in _PROGRAM_ALIASES else normalized


def _validate_payload(payload: dict[str, Any]) -> None:
    program = payload.get("program")
    if not program or not str(program).strip():
        raise ValueError("payload 'program' must be a non-empty string")

    version_number = payload.get("version_number")
    if not isinstance(version_number, int) or version_number < 1:
        raise ValueError(
            f"payload 'version_number' must be an integer >= 1, got {version_number!r}"
        )

    years = payload.get("years")
    if not isinstance(years, list):
        raise ValueError("payload 'years' must be a list")

    for year in years:
        year_number = year.get("year_number")
        if not isinstance(year_number, int) or year_number < 1:
            raise ValueError(
                f"year 'year_number' must be an integer >= 1, got {year_number!r}"
            )

        semester = year.get("semester")
        if semester is not None and semester not in (1, 2):
            raise ValueError(
                f"year {year_number} 'semester' must be None, 1, or 2, "
                f"got {semester!r}"
            )

        courses = year.get("courses")
        if not isinstance(courses, list):
            raise ValueError(f"year {year_number} 'courses' must be a list")
        for course in courses:
            course_status = course.get("course_status")
            if course_status not in _VALID_COURSE_STATUSES:
                raise ValueError(
                    f"year {year_number} course {course.get('course_code')!r} "
                    f"'course_status' must be one of {_VALID_COURSE_STATUSES}, "
                    f"got {course_status!r}"
                )


def _resolve_course_id(
    db: Any, program: str, course_code: str, course_status: str
) -> Any:
    """Resolve a co-reference to the canonical ``courses`` table for existing
    courses. Proposed courses resolve to None. A matching code owned by a
    program outside the roadmap program (or the BSInfoTech/BSIT canonical
    pair) is left unset with a warning -- never rewritten."""
    if course_status == "proposed":
        return None

    course = (
        db.query(Course)
        .filter(
            Course.course_code == course_code,
            func.lower(Course.program) == program.lower(),
        )
        .one_or_none()
    )
    if course is None:
        return None

    if _canonical_program(course.program) == _canonical_program(program):
        return course.course_id

    print(
        f"Warning: course {course_code!r} found under program "
        f"{course.program!r}, which does not match roadmap program "
        f"{program!r}; leaving course_id unset."
    )
    return None


def seed_roadmaps(db: Any, payload: dict[str, Any]) -> None:
    """Idempotent convergent seed for one roadmap version.

    The (program, specialization, version_number) roadmap is upserted and
    made the sole ``active`` roadmap for that pair. Years and courses from the
    payload are upserted (null-safe on ``semester``), and courses/years owned
    by this roadmap that are no longer in the payload are removed.
    """
    _validate_payload(payload)

    program = _canonical_program(payload["program"])
    specialization = payload.get("specialization")
    version_number = payload["version_number"]
    source_document_path = payload.get("source_document_path")

    roadmap = (
        db.query(ProgramRoadmap)
        .filter_by(
            program=program,
            specialization=specialization,
            version_number=version_number,
        )
        .one_or_none()
    )
    if roadmap is None:
        roadmap = ProgramRoadmap(
            program=program,
            specialization=specialization,
            version_number=version_number,
            status="active",
            source_document_path=source_document_path,
        )
        db.add(roadmap)
        db.flush()
    else:
        roadmap.status = "active"
        roadmap.source_document_path = source_document_path

    # At-most-one-active per (program, specialization): retire any other
    # active roadmap for the same pair.
    for other in (
        db.query(ProgramRoadmap)
        .filter(
            ProgramRoadmap.program == program,
            ProgramRoadmap.specialization == specialization,
            ProgramRoadmap.status == "active",
            ProgramRoadmap.roadmap_id != roadmap.roadmap_id,
        )
        .all()
    ):
        other.status = "retired"

    payload_year_keys: set[tuple[int, int | None]] = set()
    payload_course_codes: set[str] = set()

    for year_data in payload["years"]:
        year_number = year_data["year_number"]
        semester = year_data.get("semester")
        payload_year_keys.add((year_number, semester))

        year = (
            db.query(RoadmapYear)
            .filter(
                RoadmapYear.roadmap_id == roadmap.roadmap_id,
                RoadmapYear.year_number == year_number,
                (
                    RoadmapYear.semester.is_(None)
                    if semester is None
                    else RoadmapYear.semester == semester
                ),
            )
            .one_or_none()
        )
        if year is None:
            year = RoadmapYear(
                roadmap_id=roadmap.roadmap_id,
                year_number=year_number,
                semester=semester,
                label=year_data.get("label"),
                description=year_data.get("description"),
            )
            db.add(year)
            db.flush()
        else:
            year.label = year_data.get("label")
            year.description = year_data.get("description")

        for course_data in year_data["courses"]:
            course_code = course_data["course_code"]
            payload_course_codes.add(course_code)
            course_status = course_data["course_status"]
            course_id = _resolve_course_id(
                db, program, course_code, course_status
            )

            course = (
                db.query(RoadmapCourse)
                .filter_by(roadmap_id=roadmap.roadmap_id, course_code=course_code)
                .one_or_none()
            )
            if course is None:
                db.add(
                    RoadmapCourse(
                        roadmap_id=roadmap.roadmap_id,
                        year_id=year.year_id,
                        course_code=course_code,
                        course_title=course_data["course_title"],
                        course_id=course_id,
                        course_status=course_status,
                        tech_stack=course_data.get("tech_stack"),
                        competency_stage=course_data.get("competency_stage"),
                        learning_outcomes_summary=course_data.get(
                            "learning_outcomes_summary"
                        ),
                        portfolio_project_suggestion=course_data.get(
                            "portfolio_project_suggestion"
                        ),
                        relevant_certification=course_data.get(
                            "relevant_certification"
                        ),
                    )
                )
            else:
                course.year_id = year.year_id
                course.course_title = course_data["course_title"]
                course.course_id = course_id
                course.course_status = course_status
                course.tech_stack = course_data.get("tech_stack")
                course.competency_stage = course_data.get("competency_stage")
                course.learning_outcomes_summary = course_data.get(
                    "learning_outcomes_summary"
                )
                course.portfolio_project_suggestion = course_data.get(
                    "portfolio_project_suggestion"
                )
                course.relevant_certification = course_data.get(
                    "relevant_certification"
                )

    # Convergence (roadmap-scoped): remove courses no longer in the payload.
    for course in (
        db.query(RoadmapCourse)
        .filter(RoadmapCourse.roadmap_id == roadmap.roadmap_id)
        .all()
    ):
        if course.course_code not in payload_course_codes:
            db.delete(course)

    # Convergence: remove years no longer in the payload. Their courses go
    # with them (deleted explicitly; already-pending course deletes are a
    # no-op for SQLAlchemy).
    for year in (
        db.query(RoadmapYear)
        .filter(RoadmapYear.roadmap_id == roadmap.roadmap_id)
        .all()
    ):
        if (year.year_number, year.semester) not in payload_year_keys:
            for course in (
                db.query(RoadmapCourse)
                .filter(RoadmapCourse.year_id == year.year_id)
                .all()
            ):
                db.delete(course)
            db.delete(year)

    db.commit()

    print(
        f"Seeded program roadmap {program} / {specialization} v{version_number}: "
        f"{len(payload_year_keys)} years, {len(payload_course_codes)} courses."
    )


def main() -> None:
    from server.core.database import get_session_factory

    parser = argparse.ArgumentParser(description="Seed program roadmap data.")
    parser.add_argument(
        "--input",
        default=str(
            ROOT / "server" / "data" / "roadmaps" / "bscs_intelligent_systems.json"
        ),
        help="Path to the roadmap seed JSON.",
    )
    args = parser.parse_args()

    seed_path = Path(args.input)
    payload = json.loads(seed_path.read_text(encoding="utf-8"))

    session = get_session_factory()()
    try:
        seed_roadmaps(session, payload)
    finally:
        session.close()


if __name__ == "__main__":
    main()


__all__ = ["seed_roadmaps", "main"]
