"""Idempotent, convergent seed script for the curriculum alignment
pipeline's IT program data. Mirrors server/scripts/seed_rubrics.py's shape.

Convergence rules (safe for repeat runs):
- Courses, objectives, and map cells defined by the seed JSON are upserted:
  existing rows are corrected in place (title/description/program/level), not
  just left untouched.
- Map cells are genuinely convergent: for objectives explicitly defined by
  the seed payload, stale cells that are no longer in the canonical map are
  removed; cells for objectives outside the payload (e.g. newer IT13
  objectives) are preserved untouched.
- Legacy ``BSIT`` rows are treated as the same institutional rows as the
  canonical ``BSInfoTech`` program and normalized in place. If both a
  ``BSIT`` and a ``BSInfoTech`` row already exist for the same objective
  code, the seed fails loudly instead of silently merging two potentially
  conflicting institutional rows. A course code owned by a program outside
  BSInfoTech/BSIT is rejected, never rewritten.
- Nothing else is ever deleted: rows not described by the seed and cells on
  unseeded courses are left untouched.

Usage (from repo root):
    uv run --project server python -m server.scripts.seed_curriculum_map
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.modules.curriculum.models import (  # noqa: E402
    Course,
    CurriculumMapCell,
    CurriculumObjective,
)

#: Canonical program code; ``BSIT`` is only ever read as a legacy alias.
CANONICAL_PROGRAM = "BSInfoTech"
LEGACY_PROGRAM = "BSIT"
_PROGRAM_ALIASES = (CANONICAL_PROGRAM, LEGACY_PROGRAM)


def _objective_for_code(db: Any, code: str) -> CurriculumObjective | None:
    """Resolve an objective by code, treating BSIT as an alias of
    BSInfoTech. Fails actionably when both alias rows exist."""
    matches = (
        db.query(CurriculumObjective)
        .filter(
            CurriculumObjective.code == code,
            CurriculumObjective.program.in_(_PROGRAM_ALIASES),
        )
        .all()
    )
    if len(matches) > 1:
        raise RuntimeError(
            "Cannot normalize curriculum objective "
            f"{code!r}: both {CANONICAL_PROGRAM} and {LEGACY_PROGRAM} rows "
            "exist. Resolve the duplicate institutional objectives before "
            "re-running the seed."
        )
    return matches[0] if matches else None


def seed_curriculum_map(db: Any, payload: dict[str, Any]) -> None:
    """Idempotent convergent seed: seed-defined courses/objectives/cells are
    upserted and corrected; stale cells for known objectives are removed;
    unknown rows (and their cells) are never deleted."""
    program = payload["program"]
    if program not in _PROGRAM_ALIASES:
        raise ValueError(
            f"Unsupported program {program!r}: only {CANONICAL_PROGRAM} "
            f"(legacy alias {LEGACY_PROGRAM!r}) is supported until an "
            "authoritative BSCS map exists."
        )

    #: Codes of objectives explicitly defined by the seed payload. Cells
    #: referencing these are subject to convergence; cells referencing any
    #: other objective (e.g. a newer IT13) are preserved untouched.
    known_objective_codes = {o["code"] for o in payload["objectives"]}

    objectives_by_code: dict[str, CurriculumObjective] = {}
    for obj_data in payload["objectives"]:
        code = obj_data["code"]
        objective = _objective_for_code(db, code)
        if objective is None:
            objective = CurriculumObjective(
                code=code,
                description=obj_data["description"],
                program=CANONICAL_PROGRAM,
            )
            db.add(objective)
            db.flush()
        elif (
            objective.program != CANONICAL_PROGRAM
            or objective.description != obj_data["description"]
        ):
            objective.program = CANONICAL_PROGRAM
            objective.description = obj_data["description"]
        objectives_by_code[code] = objective

    for course_data in payload["courses"]:
        course = (
            db.query(Course)
            .filter_by(course_code=course_data["course_code"])
            .one_or_none()
        )
        if course is None:
            course = Course(
                course_code=course_data["course_code"],
                course_title=course_data["course_title"],
                program=CANONICAL_PROGRAM,
            )
            db.add(course)
            db.flush()
        elif course.program not in _PROGRAM_ALIASES:
            # The course code is owned by a different institutional program —
            # rewriting it would corrupt another program's data.
            raise RuntimeError(
                f"Course {course_data['course_code']!r} already exists under "
                f"program {course.program!r}, which is not {CANONICAL_PROGRAM} "
                f"(legacy alias {LEGACY_PROGRAM!r}). Refusing to overwrite it; "
                "resolve the conflicting course code before re-running the seed."
            )
        elif (
            course.program != CANONICAL_PROGRAM
            or course.course_title != course_data["course_title"]
        ):
            # course_code is globally unique, so this cannot collide with an
            # existing BSInfoTech row — normalizing the alias is always safe.
            course.program = CANONICAL_PROGRAM
            course.course_title = course_data["course_title"]

        #: The canonical (course -> objective level) map from the payload;
        #: blank levels are the absence of a row.
        canonical_levels = {
            code: level
            for code, level in course_data["objective_levels"].items()
            if level
        }
        for code, level in canonical_levels.items():
            objective = objectives_by_code[code]
            existing_cell = (
                db.query(CurriculumMapCell)
                .filter_by(
                    course_id=course.course_id,
                    objective_id=objective.objective_id,
                )
                .one_or_none()
            )
            if existing_cell is None:
                db.add(
                    CurriculumMapCell(
                        course_id=course.course_id,
                        objective_id=objective.objective_id,
                        level=level,
                    )
                )
            elif existing_cell.level != level:
                existing_cell.level = level

        # Convergence: drop cells for this course whose objective is a known
        # (payload) objective but is no longer mapped — the canonical map is
        # authoritative for known objectives. Cells for objectives outside the
        # payload (e.g. IT13) and cells on unseeded courses are preserved.
        for cell in (
            db.query(CurriculumMapCell).filter_by(course_id=course.course_id).all()
        ):
            objective = db.get(CurriculumObjective, cell.objective_id)
            if (
                objective is not None
                and objective.code in known_objective_codes
                and objective.program in _PROGRAM_ALIASES
                and objective.code not in canonical_levels
            ):
                db.delete(cell)

    db.commit()


def main() -> None:
    from server.core.database import get_session_factory

    seed_path = ROOT / "server" / "data" / "curriculum_map" / "it_program.json"
    payload = json.loads(seed_path.read_text(encoding="utf-8"))

    session = get_session_factory()()
    try:
        seed_curriculum_map(session, payload)
        print(f"Seeded curriculum map for program {payload['program']}.")
    finally:
        session.close()


if __name__ == "__main__":
    main()


__all__ = ["seed_curriculum_map", "main"]
