"""One-time seed script for the curriculum alignment pipeline's IT program
data. Mirrors server/scripts/seed_rubrics.py's shape.

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

from server.modules.curriculum_map.models import (  # noqa: E402
    Course,
    CurriculumMapCell,
    CurriculumObjective,
)


def seed_curriculum_map(db: Any, payload: dict[str, Any]) -> None:
    """Idempotent seed: existing rows (matched by unique code) are left
    untouched; only missing courses/objectives/cells are inserted.
    """
    program = payload["program"]

    objectives_by_code: dict[str, CurriculumObjective] = {}
    for obj_data in payload["objectives"]:
        existing = (
            db.query(CurriculumObjective)
            .filter_by(code=obj_data["code"], program=program)
            .one_or_none()
        )
        if existing is None:
            existing = CurriculumObjective(
                code=obj_data["code"],
                description=obj_data["description"],
                program=program,
            )
            db.add(existing)
            db.flush()
        objectives_by_code[obj_data["code"]] = existing

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
                program=program,
            )
            db.add(course)
            db.flush()

        for code, level in course_data["objective_levels"].items():
            if not level:
                continue  # blank cell: absence of a row, never inserted
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
