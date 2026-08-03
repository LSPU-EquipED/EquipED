"""Tests for the curriculum-map seed script against the bundled IT JSON."""

from __future__ import annotations

import json
from pathlib import Path

from server.modules.curriculum_map.models import (
    Course,
    CurriculumMapCell,
    CurriculumObjective,
)
from server.scripts import seed_curriculum_map as seed_script
from server.scripts.seed_curriculum_map import seed_curriculum_map

ROOT = Path(__file__).resolve().parents[2]
SEED_JSON = ROOT / "data" / "curriculum_map" / "it_program.json"


def test_seed_json_is_valid_and_loads() -> None:
    payload = json.loads(SEED_JSON.read_text(encoding="utf-8"))
    assert payload["program"] == "BSIT"
    assert len(payload["courses"]) >= 1
    assert len(payload["objectives"]) >= 1


def test_seed_creates_courses_objectives_and_cells(db_session) -> None:
    payload = json.loads(SEED_JSON.read_text(encoding="utf-8"))
    seed_curriculum_map(db_session, payload)

    courses = db_session.query(Course).all()
    objectives = db_session.query(CurriculumObjective).all()
    cells = db_session.query(CurriculumMapCell).all()

    assert len(courses) == len(payload["courses"])
    assert len(objectives) == len(payload["objectives"])
    expected_cell_count = sum(
        1
        for course in payload["courses"]
        for level in course["objective_levels"].values()
        if level
    )
    assert len(cells) == expected_cell_count


def test_seed_is_idempotent(db_session) -> None:
    payload = json.loads(SEED_JSON.read_text(encoding="utf-8"))
    seed_curriculum_map(db_session, payload)
    seed_curriculum_map(db_session, payload)

    courses = db_session.query(Course).all()
    assert len(courses) == len(payload["courses"])


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
