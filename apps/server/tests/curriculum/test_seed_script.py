"""Tests for the curriculum-map seed script against the bundled IT JSON."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from server.modules.curriculum.models import (
    Course,
    CurriculumMapCell,
    CurriculumObjective,
)
from server.scripts import seed_curriculum_map as seed_script
from server.scripts.seed_curriculum_map import (
    CANONICAL_PROGRAM,
    LEGACY_PROGRAM,
    seed_curriculum_map,
)

ROOT = Path(__file__).resolve().parents[2]
SEED_JSON = ROOT / "data" / "curriculum_map" / "it_program.json"


def _load_payload() -> dict:
    return json.loads(SEED_JSON.read_text(encoding="utf-8"))


def test_seed_json_is_valid_and_loads() -> None:
    payload = _load_payload()
    assert payload["program"] == CANONICAL_PROGRAM
    assert len(payload["courses"]) >= 1
    assert len(payload["objectives"]) >= 1


def test_seed_creates_courses_objectives_and_cells(db_session) -> None:
    payload = _load_payload()
    seed_curriculum_map(db_session, payload)

    courses = db_session.query(Course).all()
    objectives = db_session.query(CurriculumObjective).all()
    cells = db_session.query(CurriculumMapCell).all()

    assert len(courses) == len(payload["courses"])
    assert len(objectives) == len(payload["objectives"])
    assert all(course.program == CANONICAL_PROGRAM for course in courses)
    assert all(objective.program == CANONICAL_PROGRAM for objective in objectives)
    expected_cell_count = sum(
        1
        for course in payload["courses"]
        for level in course["objective_levels"].values()
        if level
    )
    assert len(cells) == expected_cell_count


def test_seed_is_idempotent(db_session) -> None:
    payload = _load_payload()
    seed_curriculum_map(db_session, payload)
    seed_curriculum_map(db_session, payload)

    courses = db_session.query(Course).all()
    assert len(courses) == len(payload["courses"])


def test_seed_normalizes_legacy_bsit_rows(db_session) -> None:
    """Legacy BSIT rows are read as the same institutional rows as
    BSInfoTech and normalized in place."""
    payload = _load_payload()
    seed_curriculum_map(db_session, payload)
    # Rewrite the seeded rows back to the legacy alias…
    for course in db_session.query(Course).all():
        course.program = LEGACY_PROGRAM
    for objective in db_session.query(CurriculumObjective).all():
        objective.program = LEGACY_PROGRAM
    db_session.commit()

    # …then re-seeding must converge them back to the canonical program.
    seed_curriculum_map(db_session, payload)

    assert db_session.query(Course).filter_by(program=LEGACY_PROGRAM).count() == 0
    assert (
        db_session.query(CurriculumObjective).filter_by(program=LEGACY_PROGRAM).count()
        == 0
    )
    assert db_session.query(Course).filter_by(program=CANONICAL_PROGRAM).count() == len(
        payload["courses"]
    )


def test_seed_corrects_existing_entries(db_session) -> None:
    """Convergence: known seeded entries are corrected, not just left alone."""
    payload = _load_payload()
    seed_curriculum_map(db_session, payload)

    course = (
        db_session.query(Course)
        .filter_by(course_code=payload["courses"][0]["course_code"])
        .one()
    )
    course.course_title = "Stale title"
    objective = db_session.query(CurriculumObjective).first()
    objective.description = "Stale description"
    first_cell = db_session.query(CurriculumMapCell).first()
    first_cell.level = "E" if first_cell.level != "E" else "D"
    db_session.commit()

    seed_curriculum_map(db_session, payload)

    db_session.refresh(course)
    assert course.course_title == payload["courses"][0]["course_title"]
    db_session.refresh(objective)
    assert objective.description == next(
        o["description"] for o in payload["objectives"] if o["code"] == objective.code
    )
    db_session.refresh(first_cell)
    assert first_cell.level in ("I", "E", "D")


def test_seed_does_not_delete_unknown_records(db_session) -> None:
    """Unknown rows (e.g. newer IT13 objectives) and their cells survive a
    reseed, while stale cells for known objectives are removed (see
    test_seed_removes_stale_cells_for_known_objectives)."""
    payload = _load_payload()
    seed_curriculum_map(db_session, payload)

    course = (
        db_session.query(Course)
        .filter_by(course_code=payload["courses"][0]["course_code"])
        .one()
    )
    unknown_objective = CurriculumObjective(
        code="IT13",
        description="Newer institutional outcome",
        program=CANONICAL_PROGRAM,
    )
    db_session.add(unknown_objective)
    db_session.flush()
    db_session.add(
        CurriculumMapCell(
            course_id=course.course_id,
            objective_id=unknown_objective.objective_id,
            level="D",
        )
    )
    db_session.commit()

    seed_curriculum_map(db_session, payload)

    assert db_session.query(CurriculumObjective).filter_by(code="IT13").count() == 1
    cell_count = (
        db_session.query(CurriculumMapCell)
        .filter_by(
            course_id=course.course_id,
            objective_id=unknown_objective.objective_id,
        )
        .count()
    )
    assert cell_count == 1


def test_seed_removes_stale_cells_for_known_objectives(db_session) -> None:
    """The canonical map is authoritative for known objectives: a cell for a
    payload objective that is no longer mapped is removed on reseed."""
    payload = _load_payload()
    seed_curriculum_map(db_session, payload)

    course = (
        db_session.query(Course)
        .filter_by(course_code=payload["courses"][0]["course_code"])
        .one()
    )
    # IT-INTRO maps IT03/IT07/IT10/IT11/IT12 — IT01 is a known objective that
    # is NOT in this course's canonical map, so its cell is stale.
    stale_objective = db_session.query(CurriculumObjective).filter_by(code="IT01").one()
    canonical_objective = (
        db_session.query(CurriculumObjective).filter_by(code="IT03").one()
    )
    db_session.add(
        CurriculumMapCell(
            course_id=course.course_id,
            objective_id=stale_objective.objective_id,
            level="I",
        )
    )
    db_session.commit()
    stale_cell_id = (
        db_session.query(CurriculumMapCell)
        .filter_by(
            course_id=course.course_id,
            objective_id=stale_objective.objective_id,
        )
        .one()
        .id
    )

    seed_curriculum_map(db_session, payload)

    assert (
        db_session.query(CurriculumMapCell)
        .filter_by(
            course_id=course.course_id,
            objective_id=stale_objective.objective_id,
        )
        .count()
        == 0
    )
    # Canonical cells are untouched by the cleanup.
    assert (
        db_session.query(CurriculumMapCell)
        .filter_by(
            course_id=course.course_id,
            objective_id=canonical_objective.objective_id,
        )
        .count()
        == 1
    )
    # The removed cell's row is actually gone, not just orphaned.
    assert db_session.get(CurriculumMapCell, stale_cell_id) is None


def test_seed_explicit_blank_removes_stale_cell(db_session) -> None:
    """An explicit blank level in the payload means absence of a row: a stale
    cell for that known objective is removed."""
    payload = _load_payload()
    seed_curriculum_map(db_session, payload)

    course = (
        db_session.query(Course)
        .filter_by(course_code=payload["courses"][0]["course_code"])
        .one()
    )
    objective = db_session.query(CurriculumObjective).filter_by(code="IT03").one()
    assert (
        db_session.query(CurriculumMapCell)
        .filter_by(course_id=course.course_id, objective_id=objective.objective_id)
        .count()
        == 1
    )
    # Blank out IT03 for the first course in a copy of the payload.
    blank_payload = json.loads(SEED_JSON.read_text(encoding="utf-8"))
    blank_payload["courses"][0]["objective_levels"]["IT03"] = ""

    seed_curriculum_map(db_session, blank_payload)

    assert (
        db_session.query(CurriculumMapCell)
        .filter_by(course_id=course.course_id, objective_id=objective.objective_id)
        .count()
        == 0
    )


def test_seed_rejects_course_code_owned_by_other_program(db_session) -> None:
    """A course code belonging to a program outside BSInfoTech/BSIT must be
    rejected, never rewritten to BSInfoTech."""
    payload = _load_payload()
    first = payload["courses"][0]
    # Simulate the course already existing under a foreign program.
    db_session.add(
        Course(
            course_code=first["course_code"],
            course_title=first["course_title"],
            program="BSCS",
        )
    )
    db_session.commit()

    with pytest.raises(RuntimeError, match="Refusing to overwrite"):
        seed_curriculum_map(db_session, payload)

    # The foreign row is untouched.
    foreign = (
        db_session.query(Course)
        .filter_by(course_code=first["course_code"], program="BSCS")
        .one()
    )
    assert foreign.course_title == first["course_title"]


def test_seed_fails_actionably_on_bsit_bsinfotech_duplicate(db_session) -> None:
    """Silently merging a BSIT and BSInfoTech objective with the same code
    would collapse two institutional rows — the seed must refuse."""
    payload = _load_payload()
    seed_curriculum_map(db_session, payload)

    first = db_session.query(CurriculumObjective).first()
    db_session.add(
        CurriculumObjective(
            code=first.code,
            description="Conflicting legacy row",
            program=LEGACY_PROGRAM,
        )
    )
    db_session.commit()

    with pytest.raises(RuntimeError, match="duplicate institutional objectives"):
        seed_curriculum_map(db_session, payload)


def test_seed_rejects_other_programs(db_session) -> None:
    """Only BSInfoTech (with the BSIT alias) is supported until an
    authoritative BSCS map exists."""
    payload = _load_payload()
    payload["program"] = "BSCS"

    with pytest.raises(ValueError, match="Unsupported program"):
        seed_curriculum_map(db_session, payload)


def test_main_resolves_seed_json_path_that_actually_exists() -> None:
    """Regression test: main() previously built its JSON path one directory
    too shallow (``ROOT / "data" / ...`` instead of ``ROOT / "server" /
    "data" / ...``), so ``python -m server.scripts.seed_curriculum_map``
    failed with FileNotFoundError despite every other test in this file
    passing -- those tests call ``seed_curriculum_map()`` directly with an
    independently-loaded payload and never exercise ``main()``'s path
    resolution at all.
    """
    seed_path = (
        seed_script.ROOT / "server" / "data" / "curriculum_map" / "it_program.json"
    )
    assert seed_path.is_file()
