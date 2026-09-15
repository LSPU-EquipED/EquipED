"""Offline SQLite migration tests for the program-roadmap tables
(20260808_0001).

Covers:
- Upgrading from ``20260803_0002`` (the roadmap revision's pre-advisory
  ancestor) to ``20260808_0001`` walks the conditional ``20260808_0000``
  migration, which must no-op cleanly when the ``advisory_outputs`` column
  is already present.
- The three roadmap tables exist with the expected columns, unique/check
  constraints, and indexes.
- Downgrade to ``20260808_0000`` drops the three roadmap tables.

Uses Alembic's ``alembic.command`` API with the same stamp-at-a-clean-
ancestor mechanism as the curriculum-map migration tests (the base chain is
not fully SQLite-clean for unrelated pre-roadmap revisions); SQLite tests
never touch the real database.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from alembic.command import downgrade as alembic_downgrade
from alembic.command import upgrade as alembic_upgrade
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

#: The roadmap revision under test.
ROADMAP_REV = "20260808_0001"
#: The conditional advisory migration immediately before it.
ADVISORY_REV = "20260808_0000"
#: The pre-advisory ancestor the test stamps at (a clean, SQLite-safe point
#: that already carries the ``agent_results.advisory_outputs`` column).
ANCESTOR_REV = "20260803_0002"

PROGRAM_ROADMAP_COLS = {
    "roadmap_id",
    "program",
    "specialization",
    "version_number",
    "status",
    "source_document_path",
    "created_at",
    "updated_at",
}

ROADMAP_YEARS_COLS = {
    "year_id",
    "roadmap_id",
    "year_number",
    "semester",
    "label",
    "description",
}

ROADMAP_COURSES_COLS = {
    "id",
    "roadmap_id",
    "year_id",
    "course_code",
    "course_title",
    "course_id",
    "course_status",
    "tech_stack",
    "competency_stage",
    "learning_outcomes_summary",
    "portfolio_project_suggestion",
    "relevant_certification",
}


def _cfg(db_url: str) -> Config:
    """Return an Alembic Config for the given database URL."""
    ini = str(REPO_ROOT / "server" / "alembic.ini")
    c = Config(ini)
    c.set_main_option("sqlalchemy.url", db_url.replace("%", "%%"))
    return c


def _upgrade_online(cfg: Config, target: str) -> None:
    """Run upgrade, pinning DATABASE_URL to empty so env.py uses the
    test's sqlalchemy.url instead of the real database."""
    from server.core.config import get_settings

    get_settings.cache_clear()
    old = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = ""
    try:
        alembic_upgrade(cfg, target)
    finally:
        if old is not None:
            os.environ["DATABASE_URL"] = old
        else:
            os.environ.pop("DATABASE_URL", None)
        get_settings.cache_clear()


def _downgrade_online(cfg: Config, target: str) -> None:
    """Run downgrade, pinning DATABASE_URL to empty."""
    from server.core.config import get_settings

    get_settings.cache_clear()
    old = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = ""
    try:
        alembic_downgrade(cfg, target)
    finally:
        if old is not None:
            os.environ["DATABASE_URL"] = old
        else:
            os.environ.pop("DATABASE_URL", None)
        get_settings.cache_clear()


def _current(engine) -> str | None:
    """Return the current Alembic revision stamped on *engine*."""
    from alembic.runtime.migration import MigrationContext

    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        return ctx.get_current_revision()


def _stamp(engine, revision: str) -> None:
    """Create/stamp the alembic_version table at *revision*."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS alembic_version "
                "(version_num VARCHAR(32) PRIMARY KEY)"
            )
        )
        conn.execute(text("DELETE FROM alembic_version"))
        conn.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:rev)"),
            {"rev": revision},
        )


def _create_prereq_agent_results(engine) -> None:
    """Create a minimal ``agent_results`` table carrying the
    ``advisory_outputs`` column, matching a DB already migrated to the
    ancestor revision so the conditional ``20260808_0000`` no-ops."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE agent_results ("
                "  id CHAR(32) PRIMARY KEY,"
                "  evaluation_id CHAR(32) NOT NULL,"
                "  advisory_outputs JSON"
                ")"
            )
        )


def _apply_roadmap_upgrade(tmp_path: Path) -> tuple[object, str]:
    """Stamp a fresh temp SQLite DB at the ancestor and upgrade to the
    roadmap revision, returning the engine plus its URL."""
    db = tmp_path / "roadmap_chain.db"
    db_url = f"sqlite+pysqlite:///{db}"
    engine = create_engine(db_url)
    _create_prereq_agent_results(engine)
    _stamp(engine, ANCESTOR_REV)
    engine.dispose()

    engine = create_engine(db_url)
    _upgrade_online(_cfg(db_url), ROADMAP_REV)
    return engine, db_url


def test_chain_applies_cleanly_and_creates_roadmap_tables(tmp_path) -> None:
    engine, _ = _apply_roadmap_upgrade(tmp_path)
    assert _current(engine) == ROADMAP_REV

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert {
        "program_roadmaps",
        "roadmap_years",
        "roadmap_courses",
    } <= tables

    pr_cols = {c["name"] for c in inspector.get_columns("program_roadmaps")}
    assert pr_cols == PROGRAM_ROADMAP_COLS
    ry_cols = {c["name"] for c in inspector.get_columns("roadmap_years")}
    assert ry_cols == ROADMAP_YEARS_COLS
    rc_cols = {c["name"] for c in inspector.get_columns("roadmap_courses")}
    assert rc_cols == ROADMAP_COURSES_COLS

    pr_uniq = {
        uc["name"] for uc in inspector.get_unique_constraints("program_roadmaps")
    }
    assert "uq_program_roadmaps_program_specialization_version" in pr_uniq
    pr_checks = {
        cc["name"] for cc in inspector.get_check_constraints("program_roadmaps")
    }
    assert "ck_program_roadmaps_status" in pr_checks

    ry_uniq = {uc["name"] for uc in inspector.get_unique_constraints("roadmap_years")}
    assert "uq_roadmap_years_position" in ry_uniq

    rc_checks = {
        cc["name"] for cc in inspector.get_check_constraints("roadmap_courses")
    }
    assert "ck_roadmap_courses_course_status" in rc_checks

    ry_indexes = {ix["name"] for ix in inspector.get_indexes("roadmap_years")}
    assert "idx_roadmap_years_roadmap_id" in ry_indexes
    rc_indexes = {ix["name"] for ix in inspector.get_indexes("roadmap_courses")}
    assert "idx_roadmap_courses_roadmap_code" in rc_indexes
    assert "idx_roadmap_courses_year_id" in rc_indexes

    engine.dispose()


def test_conditional_advisory_migration_noops_on_fresh_db(tmp_path) -> None:
    """The conditional ``20260808_0000`` no-ops when ``advisory_outputs`` is
    already present; only the roadmap tables are added by ``20260808_0001``."""
    db = tmp_path / "roadmap_noop.db"
    db_url = f"sqlite+pysqlite:///{db}"
    engine = create_engine(db_url)
    _create_prereq_agent_results(engine)
    _stamp(engine, ANCESTOR_REV)
    engine.dispose()

    engine = create_engine(db_url)
    _upgrade_online(_cfg(db_url), ROADMAP_REV)
    assert _current(engine) == ROADMAP_REV

    inspector = inspect(engine)
    assert "program_roadmaps" in set(inspector.get_table_names())
    agent_cols = {c["name"] for c in inspector.get_columns("agent_results")}
    assert "advisory_outputs" in agent_cols
    engine.dispose()


def test_downgrade_drops_roadmap_tables(tmp_path) -> None:
    engine, db_url = _apply_roadmap_upgrade(tmp_path)
    assert _current(engine) == ROADMAP_REV
    engine.dispose()

    engine = create_engine(db_url)
    _downgrade_online(_cfg(db_url), ADVISORY_REV)
    assert _current(engine) == ADVISORY_REV

    tables = set(inspect(engine).get_table_names())
    assert not {"program_roadmaps", "roadmap_years", "roadmap_courses"} & tables
    engine.dispose()


#: The uniqueness revision that replaces the plain roadmap-code index with a
#: UNIQUE index on (roadmap_id, course_code).
ROADMAP_CODE_UNIQUE_REV = "20260808_0002"
#: The current single head, stamped so the uniqueness revision applies alone.
CURRENT_HEAD_REV = "479684525d98"


def _apply_code_unique_upgrade(tmp_path: Path) -> tuple[object, str]:
    """Apply the roadmap tables, stamp at the current head, then upgrade to the
    uniqueness revision, returning the engine plus its URL."""
    engine, db_url = _apply_roadmap_upgrade(tmp_path)
    engine.dispose()

    engine = create_engine(db_url)
    _stamp(engine, CURRENT_HEAD_REV)
    engine.dispose()

    engine = create_engine(db_url)
    _upgrade_online(_cfg(db_url), ROADMAP_CODE_UNIQUE_REV)
    return engine, db_url


def test_code_unique_upgrade_swaps_plain_index_for_unique(tmp_path) -> None:
    engine, _ = _apply_code_unique_upgrade(tmp_path)
    assert _current(engine) == ROADMAP_CODE_UNIQUE_REV

    rc_indexes = {ix["name"] for ix in inspect(engine).get_indexes("roadmap_courses")}
    assert "uq_roadmap_courses_roadmap_code" in rc_indexes
    assert "idx_roadmap_courses_roadmap_code" not in rc_indexes
    engine.dispose()


def test_code_unique_prevents_duplicate_roadmap_course(tmp_path) -> None:
    """Inserting two RoadmapCourse rows with the same (roadmap_id,
    course_code) must raise IntegrityError after the unique index exists."""
    from sqlalchemy.exc import IntegrityError

    engine, _ = _apply_code_unique_upgrade(tmp_path)
    assert _current(engine) == ROADMAP_CODE_UNIQUE_REV

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO program_roadmaps"
                " (roadmap_id, program, specialization, version_number, status)"
                " VALUES ('00000000-0000-0000-0000-000000000001', 'BSCS',"
                " 'IS', 1, 'active')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO roadmap_years (year_id, roadmap_id, year_number)"
                " VALUES ('00000000-0000-0000-0000-000000000002',"
                " '00000000-0000-0000-0000-000000000001', 1)"
            )
        )

    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            for suffix in ("a", "b"):
                conn.execute(
                    text(
                        "INSERT INTO roadmap_courses"
                        " (id, roadmap_id, year_id, course_code, course_title,"
                        " course_status)"
                        " VALUES (:id,"
                        " '00000000-0000-0000-0000-000000000001',"
                        " '00000000-0000-0000-0000-000000000002',"
                        " 'ITEC 105', 'Course', 'existing')"
                    ),
                    {"id": f"00000000-0000-0000-0000-00000000000{suffix}"},
                )
    engine.dispose()
