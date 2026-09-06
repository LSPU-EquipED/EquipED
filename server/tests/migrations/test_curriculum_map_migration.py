"""Offline SQLite migration tests for the curriculum-map head merge and
hardening revisions (20260802_0001 / 20260802_0002).

Covers:
- The chain resolves to exactly one head after the no-op merge.
- The merge names both branch heads (20260730_0001, 20260801_0001).
- The hardening revision normalizes legacy ``BSIT`` rows to ``BSInfoTech``,
  adds nullable JSON ``provenance``, and adds the three indexes.
- Both upgrade and downgrade fail actionably when normalizing would silently
  merge conflicting institutional objective rows.
- Downgrade is fully reversible without bookkeeping tables: every canonical
  row normalizes back to ``BSIT`` so a legacy reseed cannot create
  ``(code, program)`` duplicates (migrate → seed → downgrade → legacy-reseed
  regression coverage).
- Opt-in targeted PostgreSQL coverage (``RUN_POSTGRES_MIGRATION_TESTS=1`` +
  ``TEST_DATABASE_URL``): clones only the ``documents``/``evaluation_jobs``
  structure into a throwaway ``alembic_ci_*`` schema and exercises the
  merge + hardening + minimal-seed + downgrade cycle for two deployment
  paths — current main (stamped ``20260801_0001``) and the former
  curriculum head (stamped ``20260716_0001``). The PG seed check uses a
  one-course canonical payload run twice to prove idempotency/convergence
  without the full 27-course map. The public schema must be stamped exactly
  at ``20260801_0001`` or the path refuses to run.

The live former-head compatibility test is intentionally legacy-only, non-release,
and explicitly out of CI release gates.

Uses Alembic's ``alembic.command`` API for proper context setup; SQLite tests
never touch the real database.
"""

from __future__ import annotations

import inspect as inspect_module
import io
import json
import logging
import os
import re
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import pytest
from alembic.command import downgrade as alembic_downgrade
from alembic.command import upgrade as alembic_upgrade
from alembic.config import Config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

# Ensure repo root is on sys.path so Alembic's env.py can import server modules.
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

MERGE_REV = "20260802_0001"
HARDEN_REV = "20260802_0002"
BRANCH_A = "20260730_0001"
BRANCH_B = "20260801_0001"
#: Current single head: the program-roadmap change grafted the advisory
#: repair (20260808_0000) and roadmap tables (20260808_0001) onto the
#: syllabus-alignment branch and merged it with the hardening branch, then
#: added the roadmap-course uniqueness revision (20260808_0002), then the
#: external-lineage bridge (20260810_0002), admission slot (20260811_0001),
#: SME prompt seed (20260811_0002), preference-log attribution
#: (20260811_0003), agent-result prompt-text snapshotting (20260811_0004),
#: and agent-result group_prompts snapshotting (20260814_0001), then the
#: rubric-criterion scoring_rule column (20260829_0001), then the
#: rubric-criterion GAD scoring_rule backfill (20260829_0002), then the
#: criterion-agnostic managed prompts (20260829_0005).
CHAIN_HEAD_REV = "20260902_0001"

#: Common ancestor of both feature branches; the former-curriculum head shape.
FORMER_CURRICULUM_ANCESTOR = "20260716_0001"
#: Opt-in PostgreSQL path requires this flag AND TEST_DATABASE_URL.
POSTGRES_MIGRATION_FLAG = "RUN_POSTGRES_MIGRATION_TESTS"
#: The former-head compatibility test requires this ADDITIONAL flag; it is
#: legacy-only and never release evidence.
FORMER_HEAD_COMPAT_FLAG = "RUN_POSTGRES_FORMER_HEAD_COMPAT"
#: Skip message for the former-head path when its explicit opt-in is absent.
FORMER_HEAD_COMPAT_SKIP_REASON = (
    "RUN_POSTGRES_FORMER_HEAD_COMPAT != '1': former-head path is an "
    "obsolete-head compatibility test (legacy-only), not release evidence; "
    "skipping"
)
#: The public schema must be stamped exactly here before any scenario runs.
POSTGRES_MIGRATION_BASE_REV = BRANCH_B
#: Only generated ``alembic_ci_<hex>`` schemas may be mutated by the raw
#: version-table helpers — never public or anything unvalidated.
GENERATED_SCHEMA_RE = re.compile(r"^alembic_ci_[0-9a-f]+$")

#: Standalone logger so opt-in stage timings stay visible even after
#: alembic's env.py reconfigures logging from alembic.ini. Never logs URLs.
log = logging.getLogger("equiped.postgres_migration")
if not log.handlers:
    _console = logging.StreamHandler()
    _console.setFormatter(logging.Formatter("%(levelname)-5s %(name)s: %(message)s"))
    log.addHandler(_console)
    log.setLevel(logging.INFO)
    log.propagate = False

SEED_JSON = REPO_ROOT / "server" / "data" / "curriculum_map" / "it_program.json"


def _cfg(db_url: str = "postgresql://ignored") -> Config:
    """Return an Alembic Config for the given database URL.

    Alembic's Config stores options in a ConfigParser with pyformat
    interpolation, so a raw ``%`` (e.g. percent-encoded query options
    like ``options=-csearch_path%3D<schema>``) is rejected as invalid
    interpolation syntax.  Percent signs are therefore doubled here and
    un-escaped again by the parser when the option is read back, so the
    exact URL — including any credentials — reaches Alembic unchanged.
    The URL is never logged.
    """
    ini = str(REPO_ROOT / "server" / "alembic.ini")
    c = Config(ini)
    c.set_main_option("sqlalchemy.url", db_url.replace("%", "%%"))
    return c


def _stamp(engine, revision: str) -> None:
    """Stamp the database at *revision*."""
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


def _current(engine) -> str | None:
    """Return the current Alembic revision stamped on *engine*."""
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        return ctx.get_current_revision()


def _version_heads(engine) -> set[str]:
    """Return every revision id currently stored in alembic_version.

    A branch state holds more than one head; ``_current`` only reports a
    single revision, so head-set assertions read the version table directly.
    """
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT version_num FROM alembic_version")).fetchall()
    return {row[0] for row in rows}


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
        # Drop the Settings cached while DATABASE_URL was pinned empty so a
        # later call re-reads the restored environment.
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
        # Drop the Settings cached while DATABASE_URL was pinned empty so a
        # later call re-reads the restored environment.
        get_settings.cache_clear()


def _run_offline_sql(cfg: Config, revision_range: str) -> str:
    """Run *revision_range* in offline (--sql) mode and return the SQL."""
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        alembic_upgrade(cfg, revision_range, sql=True)
    finally:
        sys.stdout = old
    return buf.getvalue()


def _create_curriculum_tables(engine) -> None:
    """Create the four curriculum-map tables exactly as 20260730_0001 does.

    Uses raw CREATE TABLE strings so the hardening migration runs against the
    pre-merge schema shape without executing the real migration chain.
    """
    from sqlalchemy import text as sql_text

    with engine.begin() as conn:
        conn.execute(
            sql_text(
                "CREATE TABLE courses ("
                "  course_id TEXT PRIMARY KEY,"
                "  course_code VARCHAR(50) NOT NULL,"
                "  course_title VARCHAR(300) NOT NULL,"
                "  program VARCHAR(50) NOT NULL,"
                "  CONSTRAINT uq_courses_course_code UNIQUE (course_code)"
                ")"
            )
        )
        conn.execute(
            sql_text(
                "CREATE TABLE curriculum_objectives ("
                "  objective_id TEXT PRIMARY KEY,"
                "  code VARCHAR(50) NOT NULL,"
                "  description TEXT NOT NULL,"
                "  program VARCHAR(50) NOT NULL,"
                "  CONSTRAINT uq_curriculum_objectives_code_program"
                "    UNIQUE (code, program)"
                ")"
            )
        )
        conn.execute(
            sql_text(
                "CREATE TABLE curriculum_map_cells ("
                "  id TEXT PRIMARY KEY,"
                "  course_id TEXT NOT NULL,"
                "  objective_id TEXT NOT NULL,"
                "  level VARCHAR(1) NOT NULL,"
                "  CONSTRAINT uq_curriculum_map_cells_course_objective"
                "    UNIQUE (course_id, objective_id),"
                "  CONSTRAINT ck_curriculum_map_cells_level"
                "    CHECK (level IN ('I', 'E', 'D'))"
                ")"
            )
        )
        conn.execute(
            sql_text(
                "CREATE TABLE curriculum_alignment_checks ("
                "  check_id TEXT PRIMARY KEY,"
                "  document_id TEXT NOT NULL,"
                "  course_id TEXT NOT NULL,"
                "  run_at DATETIME NOT NULL,"
                "  model_name VARCHAR(100),"
                "  objective_results JSON NOT NULL,"
                "  summary JSON NOT NULL,"
                "  success BOOLEAN NOT NULL DEFAULT 1,"
                "  error_message TEXT"
                ")"
            )
        )


def _seed_legacy_rows(engine) -> None:
    """Insert BSIT legacy rows plus one BSInfoTech objective/course pair."""
    from sqlalchemy import text as sql_text

    with engine.begin() as conn:
        conn.execute(
            sql_text(
                "INSERT INTO courses (course_id, course_code, course_title, program)"
                " VALUES ('c-legacy-1', 'IT-INTRO', 'Introduction to IT', 'BSIT'),"
                "        ('c-canon-1', 'IT-OOP', 'Object-Oriented Programming',"
                "         'BSInfoTech')"
            )
        )
        conn.execute(
            sql_text(
                "INSERT INTO curriculum_objectives"
                " (objective_id, code, description, program)"
                " VALUES ('o-legacy-1', 'IT01', 'Legacy desc', 'BSIT'),"
                "        ('o-legacy-2', 'IT02', 'Another legacy', 'BSIT'),"
                "        ('o-canon-1', 'IT03', 'Canonical desc', 'BSInfoTech')"
            )
        )


def _load_seed_payload() -> dict:
    return json.loads(SEED_JSON.read_text(encoding="utf-8"))


# ═══════════════════════════════════════════════════════════════════════
# Alembic Config percent-encoding regression
# ═══════════════════════════════════════════════════════════════════════


class TestAlembicConfigPercentEncoding:
    """Alembic's Config stores options in a ConfigParser with pyformat
    interpolation, so a raw ``%`` in a URL must be escaped before the
    option is set (see alembic/config.py ``set_main_option``)."""

    def test_percent_encoded_url_configures_and_round_trips(self):
        url = (
            "postgresql+psycopg2://user:p%40ss@localhost:5432/disposable_db"
            "?options=-csearch_path%3Dalembic_ci_test"
        )
        cfg = _cfg(url)
        # Interpolation un-escapes the doubled '%'; the exact original
        # URL — percent-encoded query options and credentials included —
        # comes back unchanged and is never logged.
        assert cfg.get_main_option("sqlalchemy.url") == url

    def test_raw_config_rejects_percent_encoded_url(self):
        """Guard for the defect: without escaping, ConfigParser rejects
        ``%3D`` with invalid interpolation syntax before Alembic runs."""
        c = Config(str(REPO_ROOT / "server" / "alembic.ini"))
        with pytest.raises(ValueError, match="invalid interpolation syntax"):
            c.set_main_option(
                "sqlalchemy.url",
                "postgresql+psycopg2://user:pass@localhost:5432/disposable_db"
                "?options=-csearch_path%3Dalembic_ci_test",
            )


# ═══════════════════════════════════════════════════════════════════════
# Chain structure tests
# ═══════════════════════════════════════════════════════════════════════


class TestChainStructure:
    """The migration chain is linear after the merge."""

    def test_single_head(self):
        script = ScriptDirectory.from_config(_cfg("sqlite://"))
        heads = script.get_heads()
        assert len(heads) == 1, f"Expected 1 head, got {len(heads)}: {heads}"
        assert heads == [CHAIN_HEAD_REV]

    def test_chain_contains_merge_and_hardening(self):
        script = ScriptDirectory.from_config(_cfg())
        # The merge revision has two parents, so walk both branches.
        seen: list[str] = []
        stack: list[str] = [script.get_heads()[0]]
        while stack:
            rev_id = stack.pop()
            if rev_id in seen:
                continue
            seen.append(rev_id)
            rev = script.get_revision(rev_id)
            down = rev.down_revision
            if isinstance(down, str):
                if down:
                    stack.append(down)
            else:
                stack.extend(down or ())
        assert MERGE_REV in seen
        assert HARDEN_REV in seen
        assert BRANCH_A in seen
        assert BRANCH_B in seen
        assert len(seen) == len(set(seen)), "Duplicate revision in chain"
        assert "20260507_0001" in seen

    def test_merge_revision_names_both_heads(self):
        script = ScriptDirectory.from_config(_cfg("sqlite://"))
        merge = script.get_revision(MERGE_REV)
        assert merge is not None
        assert merge.down_revision == (BRANCH_A, BRANCH_B)

    def test_hardening_revision_is_child_of_merge(self):
        script = ScriptDirectory.from_config(_cfg("sqlite://"))
        hardening = script.get_revision(HARDEN_REV)
        assert hardening is not None
        assert hardening.down_revision == MERGE_REV

    def test_upgrade_plan_from_former_head_includes_sibling_and_merge(self):
        """Alembic's true upgrade plan from the former curriculum head
        (20260730_0001) applies exactly the sibling migration 20260801_0001
        and then the no-op merge — the pair opt-in scenario 2 executes
        in-process. The plan through the head also pins the linear hardening
        step that scenario 2 runs through the normal alembic command."""
        script = ScriptDirectory.from_config(_cfg())
        plan = [
            step.revision.revision for step in script._upgrade_revs(MERGE_REV, BRANCH_A)
        ]
        assert plan == [BRANCH_B, MERGE_REV]
        full = [
            step.revision.revision
            for step in script._upgrade_revs(HARDEN_REV, BRANCH_A)
        ]
        assert full == [BRANCH_B, MERGE_REV, HARDEN_REV]


# ═══════════════════════════════════════════════════════════════════════
# Offline SQL verification (no database)
# ═══════════════════════════════════════════════════════════════════════


class TestOfflineSQL:
    """Generated DDL is correct for the merge and hardening revisions."""

    def test_merge_generates_no_schema_changes(self):
        """Walking from the curriculum-map branch through the merge emits only
        the sibling branch's DDL — the merge revision itself is a no-op."""
        sql = _run_offline_sql(_cfg(), f"{BRANCH_A}:{MERGE_REV}")
        # The sibling branch migration is the only schema change on this path.
        assert "ALTER TABLE evaluation_jobs ADD COLUMN confirmed_program" in sql
        # The merge contributes nothing of its own.
        assert "curriculum_map" not in sql
        assert "CREATE TABLE" not in sql
        assert MERGE_REV in sql

    def test_hardening_generates_normalization_and_index_ddl(self):
        sql = _run_offline_sql(_cfg(), f"{MERGE_REV}:{HARDEN_REV}")

        assert (
            "ALTER TABLE curriculum_alignment_checks ADD COLUMN provenance JSON" in sql
        ), "Hardening must add nullable JSON provenance"
        assert "CREATE INDEX idx_curriculum_map_cells_course_id" in sql
        assert "idx_curriculum_alignment_checks_document_run_at" in sql
        assert "idx_curriculum_alignment_checks_course_id" in sql
        assert "UPDATE curriculum_objectives" in sql
        assert "SET program" in sql
        assert "UPDATE courses" in sql
        assert "BSInfoTech" in sql

    def test_hardening_downgrade_offline(self):
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            alembic_downgrade(
                _cfg("postgresql://ignored"),
                f"{HARDEN_REV}:{MERGE_REV}",
                sql=True,
            )
        finally:
            sys.stdout = old
        sql = buf.getvalue()
        assert "DROP INDEX idx_curriculum_alignment_checks_course_id" in sql
        assert "DROP INDEX idx_curriculum_alignment_checks_document_run_at" in sql
        assert "DROP INDEX idx_curriculum_map_cells_course_id" in sql
        assert "ALTER TABLE curriculum_alignment_checks DROP COLUMN provenance" in sql
        # Downgrade normalizes every canonical row back to the legacy alias.
        assert "UPDATE curriculum_objectives" in sql
        assert "SET program" in sql
        assert "UPDATE courses" in sql
        assert "BSIT" in sql
        # No persistent bookkeeping tables are involved.
        assert "_tmp_" not in sql


# ═══════════════════════════════════════════════════════════════════════
# Online upgrade (temporary SQLite, stamped at the merge)
# ═══════════════════════════════════════════════════════════════════════


class TestHardeningUpgrade:
    """The hardening migration normalizes legacy rows and adds schema."""

    def _upgraded_db(self, tmp_path: Path, seed_rows: bool = True):
        db = tmp_path / "harden.db"
        db_url = f"sqlite+pysqlite:///{db}"
        engine = create_engine(db_url)
        _create_curriculum_tables(engine)
        if seed_rows:
            _seed_legacy_rows(engine)
        _stamp(engine, MERGE_REV)
        engine.dispose()

        engine = create_engine(db_url)
        _upgrade_online(_cfg(db_url), HARDEN_REV)
        return engine, db_url

    def test_normalizes_legacy_rows_and_adds_schema(self, tmp_path):
        engine, _ = self._upgraded_db(tmp_path)
        assert _current(engine) == HARDEN_REV

        with engine.connect() as conn:
            programs = {
                row[0]
                for row in conn.execute(text("SELECT program FROM courses")).fetchall()
            }
            assert programs == {"BSInfoTech"}

            objectives = conn.execute(
                text("SELECT code, program FROM curriculum_objectives")
            ).fetchall()
            assert all(row[1] == "BSInfoTech" for row in objectives)
            assert len(objectives) == 3

        inspector = inspect(engine)
        check_cols = {
            c["name"] for c in inspector.get_columns("curriculum_alignment_checks")
        }
        assert "provenance" in check_cols

        cell_ix = {ix["name"] for ix in inspector.get_indexes("curriculum_map_cells")}
        assert "idx_curriculum_map_cells_course_id" in cell_ix

        check_ix = {
            ix["name"] for ix in inspector.get_indexes("curriculum_alignment_checks")
        }
        assert "idx_curriculum_alignment_checks_document_run_at" in check_ix
        assert "idx_curriculum_alignment_checks_course_id" in check_ix
        engine.dispose()

    def test_upgrade_is_safe_on_empty_tables(self, tmp_path):
        engine, _ = self._upgraded_db(tmp_path, seed_rows=False)
        assert _current(engine) == HARDEN_REV
        inspector = inspect(engine)
        assert "provenance" in {
            c["name"] for c in inspector.get_columns("curriculum_alignment_checks")
        }
        engine.dispose()

    def test_upgrade_fails_actionably_on_duplicate_alias_rows(self, tmp_path):
        """BSIT + BSInfoTech objectives sharing a code must not be silently
        merged into one institutional row."""
        db = tmp_path / "conflict.db"
        db_url = f"sqlite+pysqlite:///{db}"
        engine = create_engine(db_url)
        _create_curriculum_tables(engine)
        from sqlalchemy import text as sql_text

        with engine.begin() as conn:
            conn.execute(
                sql_text(
                    "INSERT INTO courses (course_id, course_code, course_title,"
                    " program)"
                    " VALUES ('c-1', 'IT-INTRO', 'Introduction to IT', 'BSIT')"
                )
            )
            conn.execute(
                sql_text(
                    "INSERT INTO curriculum_objectives"
                    " (objective_id, code, description, program)"
                    " VALUES ('o-1', 'IT01', 'Legacy desc', 'BSIT'),"
                    "        ('o-2', 'IT01', 'Canonical desc', 'BSInfoTech')"
                )
            )
        _stamp(engine, MERGE_REV)
        engine.dispose()

        engine = create_engine(db_url)
        with pytest.raises(RuntimeError, match="before upgrading"):
            _upgrade_online(_cfg(db_url), HARDEN_REV)
        engine.dispose()


class TestHardeningDowngrade:
    """Downgrade drops the new schema and normalizes rows back to BSIT."""

    def test_downgrade_restores_schema_and_legacy_alias(self, tmp_path):
        db = tmp_path / "harden_down.db"
        db_url = f"sqlite+pysqlite:///{db}"
        engine = create_engine(db_url)
        _create_curriculum_tables(engine)
        _seed_legacy_rows(engine)
        _stamp(engine, MERGE_REV)
        engine.dispose()

        engine = create_engine(db_url)
        _upgrade_online(_cfg(db_url), HARDEN_REV)
        assert _current(engine) == HARDEN_REV

        _downgrade_online(_cfg(db_url), MERGE_REV)
        assert _current(engine) == MERGE_REV

        inspector = inspect(engine)
        check_cols = {
            c["name"] for c in inspector.get_columns("curriculum_alignment_checks")
        }
        assert "provenance" not in check_cols

        with engine.connect() as conn:
            # Every row — including rows that were never BSIT before upgrade —
            # is normalized back to the legacy alias.
            objectives = conn.execute(
                text("SELECT code, program FROM curriculum_objectives")
            ).fetchall()
            assert {row[0] for row in objectives} == {"IT01", "IT02", "IT03"}
            assert all(row[1] == "BSIT" for row in objectives)

            course_programs = {
                row[0]
                for row in conn.execute(text("SELECT program FROM courses")).fetchall()
            }
            assert course_programs == {"BSIT"}

            # No bookkeeping tables survive.
            tmp_tables = {
                row[0]
                for row in conn.execute(
                    text(
                        "SELECT name FROM sqlite_master"
                        " WHERE type='table' AND name LIKE '_tmp_%'"
                    )
                ).fetchall()
            }
            assert tmp_tables == set()
        engine.dispose()

    def test_downgrade_fails_actionably_on_bsit_duplicate(self, tmp_path):
        """Downgrade must refuse when normalizing BSInfoTech rows back to
        BSIT would collide with an existing BSIT row of the same code."""
        db = tmp_path / "down_conflict.db"
        db_url = f"sqlite+pysqlite:///{db}"
        engine = create_engine(db_url)
        _create_curriculum_tables(engine)
        _seed_legacy_rows(engine)
        _stamp(engine, MERGE_REV)
        engine.dispose()

        engine = create_engine(db_url)
        _upgrade_online(_cfg(db_url), HARDEN_REV)
        assert _current(engine) == HARDEN_REV

        # Introduce a BSIT objective sharing IT01 with the canonical rows.
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO curriculum_objectives"
                    " (objective_id, code, description, program)"
                    " VALUES ('o-x', 'IT01', 'Legacy duplicate', 'BSIT')"
                )
            )
        engine.dispose()

        engine = create_engine(db_url)
        with pytest.raises(RuntimeError, match="before downgrading"):
            _downgrade_online(_cfg(db_url), MERGE_REV)
        engine.dispose()

    def test_migrate_seed_downgrade_legacy_reseed(self, tmp_path):
        """Full lifecycle regression: upgrade → canonical seed → downgrade →
        legacy BSIT reseed. The downgrade normalizes every row back to BSIT
        so the legacy reseed cannot create (code, program) duplicates."""
        from server.scripts.seed_curriculum_map import seed_curriculum_map

        db = tmp_path / "seed_cycle.db"
        db_url = f"sqlite+pysqlite:///{db}"
        engine = create_engine(db_url)
        _create_curriculum_tables(engine)
        _stamp(engine, MERGE_REV)
        engine.dispose()

        engine = create_engine(db_url)
        _upgrade_online(_cfg(db_url), HARDEN_REV)
        assert _current(engine) == HARDEN_REV

        # 1) Seed the canonical BSInfoTech map.
        payload = _load_seed_payload()
        session = sessionmaker(bind=engine, autoflush=False)()
        seed_curriculum_map(session, payload)
        session.close()
        with engine.connect() as conn:
            seeded_courses = conn.execute(text("SELECT COUNT(*) FROM courses")).scalar()
            seeded_objectives = conn.execute(
                text("SELECT COUNT(*) FROM curriculum_objectives")
            ).scalar()
        assert seeded_courses == len(payload["courses"])
        assert seeded_objectives == len(payload["objectives"])

        # 2) Downgrade to the merge: everything normalizes back to BSIT.
        _downgrade_online(_cfg(db_url), MERGE_REV)
        assert _current(engine) == MERGE_REV
        with engine.connect() as conn:
            objective_programs = {
                row[0]
                for row in conn.execute(
                    text("SELECT DISTINCT program FROM curriculum_objectives")
                ).fetchall()
            }
            course_programs = {
                row[0]
                for row in conn.execute(
                    text("SELECT DISTINCT program FROM courses")
                ).fetchall()
            }
        assert objective_programs == {"BSIT"}
        assert course_programs == {"BSIT"}

        # 3) Legacy reseed (BSIT payload) must converge without duplicates.
        legacy_payload = _load_seed_payload()
        legacy_payload["program"] = "BSIT"
        session2 = sessionmaker(bind=engine, autoflush=False)()
        seed_curriculum_map(session2, legacy_payload)
        session2.close()

        with engine.connect() as conn:
            assert (
                conn.execute(text("SELECT COUNT(*) FROM courses")).scalar()
                == seeded_courses
            )
            assert (
                conn.execute(
                    text("SELECT COUNT(*) FROM curriculum_objectives")
                ).scalar()
                == seeded_objectives
            )
            objective_programs = {
                row[0]
                for row in conn.execute(
                    text("SELECT DISTINCT program FROM curriculum_objectives")
                ).fetchall()
            }
            course_programs = {
                row[0]
                for row in conn.execute(
                    text("SELECT DISTINCT program FROM courses")
                ).fetchall()
            }
        assert objective_programs == {"BSInfoTech"}
        assert course_programs == {"BSInfoTech"}
        engine.dispose()


# ═══════════════════════════════════════════════════════════════════════
# Opt-in PostgreSQL migration path
# ═══════════════════════════════════════════════════════════════════════


def _postgres_guard() -> str | None:
    """Return a skip reason unless the opt-in PG environment is ready."""
    if os.environ.get(POSTGRES_MIGRATION_FLAG) != "1":
        return "RUN_POSTGRES_MIGRATION_TESTS != '1'; skipping PostgreSQL path"
    base_url = os.environ.get("TEST_DATABASE_URL")
    if not base_url:
        return "TEST_DATABASE_URL not set; skipping PostgreSQL path"
    if make_url(base_url).get_backend_name() != "postgresql":
        return "TEST_DATABASE_URL is not a PostgreSQL URL; skipping PostgreSQL path"
    return None


def _former_head_compat_guard() -> str | None:
    """Return a skip reason unless the former-head compat opt-in is set.

    The former-curriculum-head path is obsolete-head compatibility coverage
    only and must never be treated as release evidence; it is gated by its
    own explicit flag and skipped (visibly) otherwise.
    """
    if os.environ.get(FORMER_HEAD_COMPAT_FLAG) != "1":
        return FORMER_HEAD_COMPAT_SKIP_REASON
    return None


@contextmanager
def _stage(label: str):
    """Log how long one opt-in migration/seed stage took."""
    start = time.monotonic()
    try:
        yield
    finally:
        log.info("%s: %.1fs", label, time.monotonic() - start)


def _direct_url(base_url: str) -> URL:
    """Return the direct (unpooled) endpoint URL for *base_url*.

    Neon pooler endpoints embed ``-pooler`` in the hostname; session-level
    connection options (search_path, timeouts) require the direct endpoint.
    """
    url = make_url(base_url)
    host = url.host or ""
    if "-pooler" in host:
        url = url.set(host=host.replace("-pooler", ""))
    return url.update_query_dict({"connect_timeout": "10"})


def _scoped_url(base_url: str, schema: str) -> URL:
    """Build a schema-scoped URL with connect/statement/lock timeouts.

    The generated schema becomes the connection's search_path (public is
    excluded), with a 10s connect timeout, 60s statement timeout, and 5s
    lock timeout. ``application_name`` carries the schema so sessions show up
    cleanly in pg_stat_activity without exposing the URL or credentials.
    SQLAlchemy percent-encodes the option values; ``_cfg``'s ConfigParser
    escaping round-trips them unchanged.
    """
    options = f"-csearch_path={schema} -cstatement_timeout=60000 -clock_timeout=5000"
    return _direct_url(base_url).update_query_dict(
        {"options": options, "application_name": f"equiped_migration_{schema}"}
    )


def _assert_schema_scoped(url: URL, schema: str) -> None:
    """Assert a connection on *url* resolves *schema* with scoped timeouts."""
    engine = create_engine(url, poolclass=NullPool)
    try:
        with engine.connect() as conn:
            assert conn.execute(text("SELECT current_schema()")).scalar() == schema
            search_path = conn.execute(text("SHOW search_path")).scalar() or ""
            parts = [part.strip().strip('"') for part in search_path.split(",")]
            assert schema in parts
            assert "public" not in parts
            assert conn.execute(text("SHOW statement_timeout")).scalar() == "1min"
            assert conn.execute(text("SHOW lock_timeout")).scalar() == "5s"
            assert conn.execute(text("SHOW application_name")).scalar() == (
                f"equiped_migration_{schema}"
            )
    finally:
        engine.dispose()


def _public_revision(engine) -> str | None:
    """Return the single public alembic_version, or None when absent/ambiguous."""
    with engine.connect() as conn:
        try:
            rows = conn.execute(
                text("SELECT version_num FROM public.alembic_version")
            ).fetchall()
        except Exception:
            return None
    if len(rows) != 1:
        return None
    return rows[0][0]


def _insert_minimal_bsit_rows(engine, course_code: str, objective_code: str) -> None:
    """Insert one BSIT course and one BSIT objective into the scoped schema."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO courses (course_id, course_code, course_title, program)"
                " VALUES (:cid, :course_code, :title, 'BSIT')"
            ),
            {
                "cid": str(uuid.uuid4()),
                "course_code": course_code,
                "title": "Legacy minimal course",
            },
        )
        conn.execute(
            text(
                "INSERT INTO curriculum_objectives"
                " (objective_id, code, description, program)"
                " VALUES (:oid, :objective_code, :desc, 'BSIT')"
            ),
            {
                "oid": str(uuid.uuid4()),
                "objective_code": objective_code,
                "desc": "Legacy minimal objective",
            },
        )


def _minimal_seed_payload() -> dict:
    """One-course canonical payload for fast PG seed convergence checks.

    Keeps the opt-in seed stage to a handful of round trips (the full
    27-course map stays covered by the local SQLite tests).
    """
    return {
        "program": "BSInfoTech",
        "objectives": [{"code": "IT01", "description": "Minimal canonical objective"}],
        "courses": [
            {
                "course_code": "MIN-CSE101",
                "course_title": "Minimal Canonical Course",
                "objective_levels": {"IT01": "I"},
            }
        ],
    }


def _apply_revision_ddl(engine, script: ScriptDirectory, revision: str) -> None:
    """Run one revision's real ``upgrade()`` and commit — no stamp.

    The revision module is looked up on *script* (never imported by numeric
    filename). Its ``upgrade()`` runs against the live connection through an
    ``Operations`` context and commits independently. The version table is
    left untouched; heads are managed separately by the schema-scoped raw
    helpers below, because alembic's live stamp/HeadMaintainer machinery
    hangs against the Neon direct endpoint.
    """
    rev = script.get_revision(revision)
    assert rev is not None, f"unknown revision {revision}"
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            rev.module.upgrade()


def _assert_generated_schema(schema: str) -> None:
    """Refuse raw version-table mutation unless *schema* is a generated
    ``alembic_ci_<hex>`` name — never public or anything unvalidated."""
    if not GENERATED_SCHEMA_RE.fullmatch(schema):
        raise AssertionError(
            f"refusing raw version-table mutation on non-generated schema {schema!r}"
        )


def _check_heads(actual: set[str], expected: set[str], operation: str) -> None:
    """Assert the version-table heads match exactly before mutating."""
    if actual != expected:
        raise AssertionError(
            f"{operation}: expected version heads {sorted(expected)}, "
            f"found {sorted(actual)}"
        )


def _locked_version_rows(conn, schema: str) -> set[str]:
    """Return ``<schema>.alembic_version`` heads, locking them FOR UPDATE."""
    rows = conn.execute(
        text(f'SELECT version_num FROM "{schema}".alembic_version FOR UPDATE')
    ).fetchall()
    return {row[0] for row in rows}


def _add_sibling_head(engine, schema: str, revision: str) -> None:
    """Append *revision* to ``<schema>.alembic_version`` as a second head.

    Models alembic's HeadMaintainer branch-create step: lock the generated
    schema's version rows FOR UPDATE, assert the exact single current head
    ``{BRANCH_A}``, then INSERT the sibling row.
    """
    _assert_generated_schema(schema)
    with engine.begin() as conn:
        _check_heads(_locked_version_rows(conn, schema), {BRANCH_A}, "add sibling head")
        conn.execute(
            text(f'INSERT INTO "{schema}".alembic_version (version_num) VALUES (:rev)'),
            {"rev": revision},
        )


def _collapse_merge_heads(
    engine, schema: str, parents: tuple[str, ...], merge_revision: str
) -> None:
    """Collapse the two parent heads into the no-op merge revision.

    Models alembic's HeadMaintainer merge_branch_idents bookkeeping without
    the live machinery: lock the generated schema's version rows FOR UPDATE,
    assert exactly the two parent heads, DELETE both parent rows (rowcount-
    checked), and INSERT the merge revision.
    """
    _assert_generated_schema(schema)
    with engine.begin() as conn:
        _check_heads(_locked_version_rows(conn, schema), set(parents), "collapse merge")
        deleted = conn.execute(
            text(
                f'DELETE FROM "{schema}".alembic_version'
                " WHERE version_num IN (:r1, :r2)"
            ),
            {"r1": parents[0], "r2": parents[1]},
        )
        assert deleted.rowcount == 2, (
            f"expected to delete exactly the 2 parent heads, deleted {deleted.rowcount}"
        )
        conn.execute(
            text(f'INSERT INTO "{schema}".alembic_version (version_num) VALUES (:rev)'),
            {"rev": merge_revision},
        )


@dataclass(frozen=True)
class PgSchemaContext:
    """Disposable schema plus its scoped, direct-endpoint URL."""

    schema: str
    url: URL

    @property
    def rendered_url(self) -> str:
        # Carries credentials; never log this value.
        return self.url.render_as_string(hide_password=False)


@pytest.fixture(scope="function")
def pg_isolated_schema():
    """Create a throwaway schema cloning only documents/evaluation_jobs.

    Skipped unless the opt-in PG environment is present. Refuses to run when
    the public schema is not stamped exactly at the authorized current-main
    revision (20260801_0001); every migration in the scenarios applies inside
    the generated schema only, and teardown asserts the public revision is
    unchanged.
    """
    reason = _postgres_guard()
    if reason:
        pytest.skip(reason)

    base_url = os.environ["TEST_DATABASE_URL"]
    direct = _direct_url(base_url)
    schema = f"alembic_ci_{uuid.uuid4().hex[:12]}"
    admin_engine = create_engine(
        direct, poolclass=NullPool, isolation_level="AUTOCOMMIT"
    )
    ran = False
    try:
        public_rev = _public_revision(admin_engine)
        if public_rev != POSTGRES_MIGRATION_BASE_REV:
            pytest.skip(
                f"public.alembic_version is {public_rev!r}, expected "
                f"{POSTGRES_MIGRATION_BASE_REV!r}; refusing to run migrations "
                "outside the authorized branch"
            )
        with admin_engine.connect() as conn:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            conn.execute(
                text(
                    f'CREATE TABLE "{schema}".documents'
                    " (LIKE public.documents INCLUDING ALL)"
                )
            )
            conn.execute(
                text(
                    f'CREATE TABLE "{schema}".evaluation_jobs'
                    " (LIKE public.evaluation_jobs INCLUDING ALL)"
                )
            )
        url = _scoped_url(base_url, schema)
        _assert_schema_scoped(url, schema)
        ran = True
        yield PgSchemaContext(schema=schema, url=url)
    finally:
        with admin_engine.connect() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()
        # Only a real run must prove the public schema stayed untouched.
        if ran:
            verify = create_engine(
                direct, poolclass=NullPool, isolation_level="AUTOCOMMIT"
            )
            try:
                assert _public_revision(verify) == POSTGRES_MIGRATION_BASE_REV, (
                    "public.alembic_version drifted from the authorized "
                    f"{POSTGRES_MIGRATION_BASE_REV} revision"
                )
            finally:
                verify.dispose()


class TestPostgresMigrationPath:
    """Opt-in targeted PostgreSQL migration coverage.

    Requires ``RUN_POSTGRES_MIGRATION_TESTS=1`` plus ``TEST_DATABASE_URL``
    pointing at a *disposable* PostgreSQL branch. PRE-UPGRADE CONDITION: the
    branch's ``public.alembic_version`` must contain exactly ``20260801_0001``
    (current main); anything else is refused with a skip. Each run creates and
    drops a throwaway ``alembic_ci_*`` schema that clones only the structure
    of ``public.documents`` and ``public.evaluation_jobs``; the database is
    never touched outside that schema. Connections use the direct (unpooled)
    endpoint with search_path pinned to the generated schema (public
    excluded), effective ``statement_timeout=1min`` / ``lock_timeout=5s``,
    and an ``application_name`` scoped to the generated schema for safe
    pg_stat_activity diagnosis.

    ``test_current_main_deployment_path`` is the RELEASE GATE: all deployment
    targets must sit exactly at 20260801_0001, so this is the only live PG
    test the release command runs. It covers the current-main deployment path
    (stamped at 20260801_0001): merge upgrade, hardening upgrade, a minimal
    one-course canonical seed run twice to prove PG seed idempotency/
    convergence, then a downgrade.

    ``test_former_curriculum_head_path`` is obsolete-head COMPATIBILITY
    coverage only — legacy-only, NOT release evidence — and requires the
    second explicit flag ``RUN_POSTGRES_FORMER_HEAD_COMPAT=1``; without it the
    test skips visibly with a clear message. It covers the former-curriculum
    head (stamped at 20260716_0001) that predates ``confirmed_program``: it
    applies the real sibling 20260801_0001 DDL through an in-process
    ``Operations`` context and then forms/collapses the two Alembic heads with
    narrowly encapsulated raw version-table helpers, and independently
    exercises the hardening upgrade. It deliberately does NOT exercise
    Alembic's live HeadMaintainer branch/merge machinery — the branch-merge
    command and ``MigrationContext.stamp`` repeatedly hang against the Neon
    direct endpoint — so the true graph is pinned by the static plan test
    (``test_upgrade_plan_from_former_head_includes_sibling_and_merge``) and
    the offline no-DDL merge proof (``test_merge_generates_no_schema_changes``)
    instead. Stage durations are logged through the
    ``equiped.postgres_migration`` logger; no URLs or credentials are ever
    logged.

    Release invocation (from ``server/``) — the command MUST target exactly
    the release-gate method, and should run under a strict wall-clock timeout
    so a hang can never pass silently (a fixed 300s deadline; adjust to the
    slowest authorized branch)::

        RUN_POSTGRES_MIGRATION_TESTS=1 TEST_DATABASE_URL=... \\
            timeout 300 uv run pytest \\
            tests/migrations/test_curriculum_map_migration.py \\
            ::TestPostgresMigrationPath::test_current_main_deployment_path -q

    Optional full-compat invocation (adds the legacy former-head path)::

        RUN_POSTGRES_MIGRATION_TESTS=1 \\
        RUN_POSTGRES_FORMER_HEAD_COMPAT=1 TEST_DATABASE_URL=... \\
            timeout 600 uv run pytest \\
            tests/migrations/test_curriculum_map_migration.py \\
            ::TestPostgresMigrationPath -q
    """

    def test_current_main_deployment_path(self, pg_isolated_schema):
        ctx = pg_isolated_schema
        rendered = ctx.rendered_url

        engine = create_engine(ctx.url, poolclass=NullPool)
        _assert_schema_scoped(ctx.url, ctx.schema)
        _stamp(engine, BRANCH_B)
        engine.dispose()

        # Merge upgrade applies the curriculum-map branch on top of main.
        with _stage("merge upgrade"):
            _upgrade_online(_cfg(rendered), MERGE_REV)
        engine = create_engine(ctx.url, poolclass=NullPool)
        assert _current(engine) == MERGE_REV
        tables = set(inspect(engine).get_table_names())
        assert {
            "courses",
            "curriculum_objectives",
            "curriculum_map_cells",
            "curriculum_alignment_checks",
        } <= tables
        eval_cols = [c["name"] for c in inspect(engine).get_columns("evaluation_jobs")]
        assert eval_cols.count("confirmed_program") == 1
        _insert_minimal_bsit_rows(engine, "ZZ-LEGACY-1", "IT90")
        engine.dispose()

        # Hardening normalizes the legacy alias, adds nullable provenance,
        # and creates exactly the three intended indexes.
        with _stage("hardening upgrade"):
            _upgrade_online(_cfg(rendered), HARDEN_REV)
        engine = create_engine(ctx.url, poolclass=NullPool)
        assert _current(engine) == HARDEN_REV
        with engine.connect() as conn:
            assert {
                row[0]
                for row in conn.execute(text("SELECT DISTINCT program FROM courses"))
            } == {"BSInfoTech"}
            assert {
                row[0]
                for row in conn.execute(
                    text("SELECT DISTINCT program FROM curriculum_objectives")
                )
            } == {"BSInfoTech"}
        provenance = next(
            c
            for c in inspect(engine).get_columns("curriculum_alignment_checks")
            if c["name"] == "provenance"
        )
        assert provenance["nullable"] is True
        cell_ix = {
            ix["name"] for ix in inspect(engine).get_indexes("curriculum_map_cells")
        }
        check_ix = {
            ix["name"]
            for ix in inspect(engine).get_indexes("curriculum_alignment_checks")
        }
        assert cell_ix == {
            "idx_curriculum_map_cells_course_id",
            "uq_curriculum_map_cells_course_objective",
        }
        assert check_ix == {
            "idx_curriculum_alignment_checks_document_run_at",
            "idx_curriculum_alignment_checks_course_id",
        }

        # Minimal canonical seed, run twice: proves PG seed idempotency and
        # convergence, with the pre-hardening BSIT rows normalized in place.
        from server.scripts.seed_curriculum_map import seed_curriculum_map

        payload = _minimal_seed_payload()
        seeded_states = []
        with _stage("minimal seed (x2)"):
            for _ in range(2):
                session = sessionmaker(bind=engine, autoflush=False)()
                seed_curriculum_map(session, payload)
                session.close()
                with engine.connect() as conn:
                    seeded_states.append(
                        {
                            "courses": conn.execute(
                                text("SELECT COUNT(*) FROM courses")
                            ).scalar(),
                            "objectives": conn.execute(
                                text("SELECT COUNT(*) FROM curriculum_objectives")
                            ).scalar(),
                            "cells": conn.execute(
                                text("SELECT COUNT(*) FROM curriculum_map_cells")
                            ).scalar(),
                            "levels": {
                                row[0]
                                for row in conn.execute(
                                    text("SELECT level FROM curriculum_map_cells")
                                ).fetchall()
                            },
                        }
                    )
        assert seeded_states[0] == seeded_states[1], (
            "second seed changed state; PG seed is not idempotent"
        )
        seeded = seeded_states[0]
        # +1 for the minimal course/objective inserted before hardening.
        assert seeded["courses"] == len(payload["courses"]) + 1
        assert seeded["objectives"] == len(payload["objectives"]) + 1
        assert seeded["cells"] == 1
        assert seeded["levels"] == {"I"}
        engine.dispose()

        # Downgrade removes hardening schema and normalizes every row back to
        # BSIT with stable counts and no alias duplicates.
        with _stage("downgrade"):
            _downgrade_online(_cfg(rendered), MERGE_REV)
        engine = create_engine(ctx.url, poolclass=NullPool)
        assert _current(engine) == MERGE_REV
        check_cols = {
            c["name"]
            for c in inspect(engine).get_columns("curriculum_alignment_checks")
        }
        assert "provenance" not in check_cols
        cell_ix = {
            ix["name"] for ix in inspect(engine).get_indexes("curriculum_map_cells")
        }
        check_ix = {
            ix["name"]
            for ix in inspect(engine).get_indexes("curriculum_alignment_checks")
        }
        assert "idx_curriculum_map_cells_course_id" not in cell_ix
        assert "idx_curriculum_alignment_checks_document_run_at" not in check_ix
        assert "idx_curriculum_alignment_checks_course_id" not in check_ix
        with engine.connect() as conn:
            assert {
                row[0]
                for row in conn.execute(text("SELECT DISTINCT program FROM courses"))
            } == {"BSIT"}
            assert {
                row[0]
                for row in conn.execute(
                    text("SELECT DISTINCT program FROM curriculum_objectives")
                )
            } == {"BSIT"}
            assert (
                conn.execute(text("SELECT COUNT(*) FROM courses")).scalar()
                == seeded["courses"]
            )
            assert (
                conn.execute(
                    text("SELECT COUNT(*) FROM curriculum_objectives")
                ).scalar()
                == seeded["objectives"]
            )
            assert (
                conn.execute(text("SELECT COUNT(*) FROM curriculum_map_cells")).scalar()
                == 1
            )
            dup_codes = conn.execute(
                text(
                    "SELECT code FROM curriculum_objectives"
                    " GROUP BY code HAVING COUNT(*) > 1"
                )
            ).fetchall()
            assert dup_codes == []
            dup_courses = conn.execute(
                text(
                    "SELECT course_code FROM courses"
                    " GROUP BY course_code HAVING COUNT(*) > 1"
                )
            ).fetchall()
            assert dup_courses == []
        engine.dispose()

    @pytest.mark.skipif(
        _former_head_compat_guard() is not None,
        reason=FORMER_HEAD_COMPAT_SKIP_REASON,
    )
    def test_former_curriculum_head_path(self, pg_isolated_schema):
        """Obsolete-head compatibility path — NOT release evidence.

        Former curriculum heads are legacy-only; every deployment target is
        required to sit exactly at ``20260801_0001``, so this path is gated
        behind ``RUN_POSTGRES_FORMER_HEAD_COMPAT=1`` and skipped visibly
        otherwise. Static/offline coverage of the former-head graph lives in
        ``TestChainStructure`` and ``TestOfflineSQL`` regardless.
        """
        ctx = pg_isolated_schema
        rendered = ctx.rendered_url

        engine = create_engine(ctx.url, poolclass=NullPool)
        _assert_schema_scoped(ctx.url, ctx.schema)
        # Simulate the pre-confirmed_program shape on the clone.
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE evaluation_jobs DROP COLUMN confirmed_program")
            )
        _stamp(engine, FORMER_CURRICULUM_ANCESTOR)
        engine.dispose()

        # Upgrade only to the curriculum-map branch head.
        with _stage("branch-A upgrade"):
            _upgrade_online(_cfg(rendered), BRANCH_A)
        engine = create_engine(ctx.url, poolclass=NullPool)
        assert _current(engine) == BRANCH_A
        assert _version_heads(engine) == {BRANCH_A}
        tables = set(inspect(engine).get_table_names())
        assert {
            "courses",
            "curriculum_objectives",
            "curriculum_map_cells",
            "curriculum_alignment_checks",
        } <= tables
        eval_cols = [c["name"] for c in inspect(engine).get_columns("evaluation_jobs")]
        assert "confirmed_program" not in eval_cols
        _insert_minimal_bsit_rows(engine, "ZZ-LEGACY-2", "IT91")
        engine.dispose()

        # Former-head -> merge semantics. Alembic's true plan for
        # {20260730_0001} -> 20260802_0001 is [20260801_0001, 20260802_0001]
        # (TestChainStructure::test_upgrade_plan_from_former_head_includes_
        # sibling_and_merge) and the merge is proven DDL-free offline
        # (TestOfflineSQL::test_merge_generates_no_schema_changes). Driving
        # that branch-merge through alembic's live machinery — the command or
        # MigrationContext.stamp — repeatedly hangs against the Neon direct
        # endpoint, so scenario 2 validates the REAL sibling DDL plus the
        # exact version-table metadata state with narrow raw helpers. It does
        # not exercise live HeadMaintainer; that path is pinned by the static
        # graph tests above.
        script = ScriptDirectory.from_config(_cfg())
        engine = create_engine(ctx.url, poolclass=NullPool)
        with _stage("sibling upgrade (20260801_0001)"):
            _apply_revision_ddl(engine, script, BRANCH_B)
        # Sibling DDL committed independently; the version head is untouched
        # and still the curriculum head {BRANCH_A}.
        assert _version_heads(engine) == {BRANCH_A}
        confirmed = [
            c
            for c in inspect(engine).get_columns("evaluation_jobs")
            if c["name"] == "confirmed_program"
        ]
        assert len(confirmed) == 1
        assert confirmed[0]["nullable"] is True
        assert str(confirmed[0]["type"]) == "VARCHAR(50)"
        # Curriculum tables and the pre-inserted legacy rows survive.
        with engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM courses")).scalar() == 1
            assert (
                conn.execute(
                    text("SELECT COUNT(*) FROM curriculum_objectives")
                ).scalar()
                == 1
            )
        # Raw bookkeeping: append the sibling head, then collapse both parents
        # into the merge revision.
        with _stage("add sibling head (20260801_0001)"):
            _add_sibling_head(engine, ctx.schema, BRANCH_B)
        assert _version_heads(engine) == {BRANCH_A, BRANCH_B}
        with _stage("merge collapse (20260802_0001)"):
            _apply_revision_ddl(engine, script, MERGE_REV)
            _collapse_merge_heads(engine, ctx.schema, (BRANCH_A, BRANCH_B), MERGE_REV)
        assert _version_heads(engine) == {MERGE_REV}
        engine.dispose()

        # Hardening normalizes the legacy alias and adds schema.
        with _stage("hardening upgrade"):
            _upgrade_online(_cfg(rendered), HARDEN_REV)
        engine = create_engine(ctx.url, poolclass=NullPool)
        assert _current(engine) == HARDEN_REV
        with engine.connect() as conn:
            assert {
                row[0]
                for row in conn.execute(text("SELECT DISTINCT program FROM courses"))
            } == {"BSInfoTech"}
            assert {
                row[0]
                for row in conn.execute(
                    text("SELECT DISTINCT program FROM curriculum_objectives")
                )
            } == {"BSInfoTech"}
        provenance = next(
            c
            for c in inspect(engine).get_columns("curriculum_alignment_checks")
            if c["name"] == "provenance"
        )
        assert provenance["nullable"] is True
        cell_ix = {
            ix["name"] for ix in inspect(engine).get_indexes("curriculum_map_cells")
        }
        check_ix = {
            ix["name"]
            for ix in inspect(engine).get_indexes("curriculum_alignment_checks")
        }
        assert "idx_curriculum_map_cells_course_id" in cell_ix
        assert "idx_curriculum_alignment_checks_document_run_at" in check_ix
        assert "idx_curriculum_alignment_checks_course_id" in check_ix
        engine.dispose()


class TestPostgresFixtureGuards:
    """Unit coverage for the opt-in PG guard and URL construction (no DB)."""

    def test_guard_skips_without_flag(self, monkeypatch):
        monkeypatch.delenv(POSTGRES_MIGRATION_FLAG, raising=False)
        monkeypatch.setenv("TEST_DATABASE_URL", "postgresql://user:pass@host/db")
        assert _postgres_guard() is not None

    def test_guard_skips_without_url(self, monkeypatch):
        monkeypatch.setenv(POSTGRES_MIGRATION_FLAG, "1")
        monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
        assert _postgres_guard() is not None

    def test_guard_skips_non_postgres_url(self, monkeypatch):
        monkeypatch.setenv(POSTGRES_MIGRATION_FLAG, "1")
        monkeypatch.setenv("TEST_DATABASE_URL", "sqlite:///tmp/unused.db")
        assert _postgres_guard() is not None

    def test_guard_ok_when_flag_and_postgres_url(self, monkeypatch):
        monkeypatch.setenv(POSTGRES_MIGRATION_FLAG, "1")
        monkeypatch.setenv("TEST_DATABASE_URL", "postgresql://user:pass@host/db")
        assert _postgres_guard() is None

    def test_former_head_compat_guard_skips_without_flag(self, monkeypatch):
        monkeypatch.delenv(FORMER_HEAD_COMPAT_FLAG, raising=False)
        reason = _former_head_compat_guard()
        assert reason is not None
        assert "not release evidence" in reason
        assert "obsolete-head" in reason
        reason_lower = reason.lower()
        assert "former head" in reason_lower or "former-head" in reason_lower
        assert "legacy" in reason_lower
        assert "obsolete" in reason_lower

    def test_former_head_compat_guard_ok_with_flag(self, monkeypatch):
        monkeypatch.setenv(FORMER_HEAD_COMPAT_FLAG, "1")
        assert _former_head_compat_guard() is None

    def test_former_head_skipif_markers_are_only_on_former_head_path(self) -> None:
        module = sys.modules[__name__]
        skipif_targets: list[str] = []

        def _collect_skipif(pytest_mark_target: str, target: object) -> None:
            marks = getattr(target, "pytestmark", ())
            for mark in marks:
                if getattr(mark, "name", None) != "skipif":
                    continue
                reason = ""
                if mark.args and isinstance(mark.args[0], str):
                    reason = mark.args[0]
                elif isinstance(mark.kwargs.get("reason"), str):
                    reason = str(mark.kwargs["reason"])
                else:
                    continue

                reason_lower = reason.lower()
                assert (
                    "former head" in reason_lower
                    or "former-head" in reason_lower
                    or "obsolete" in reason_lower
                    or "legacy" in reason_lower
                ), "former-head skip reason wording changed"
                skipif_targets.append(pytest_mark_target)

        for name, obj in inspect_module.getmembers(module, inspect_module.isfunction):
            _collect_skipif(name, obj)
        for class_name, class_obj in inspect_module.getmembers(
            module, inspect_module.isclass
        ):
            if class_obj.__module__ != module.__name__:
                continue
            for meth_name, meth in inspect_module.getmembers(
                class_obj, inspect_module.isfunction
            ):
                _collect_skipif(f"{class_name}.{meth_name}", meth)

        assert skipif_targets == [
            "TestPostgresMigrationPath.test_former_curriculum_head_path"
        ]

    def test_direct_url_strips_pooler_suffix(self):
        url = _direct_url(
            "postgresql+psycopg2://u:p@ep-x-abc-pooler.c-5.us-east-1.aws.neon.tech/db"
        )
        assert url.host == "ep-x-abc.c-5.us-east-1.aws.neon.tech"

    def test_direct_url_keeps_direct_host(self):
        url = _direct_url(
            "postgresql+psycopg2://u:p@ep-x-abc.c-5.us-east-1.aws.neon.tech/db"
        )
        assert url.host == "ep-x-abc.c-5.us-east-1.aws.neon.tech"

    def test_scoped_url_pins_search_path_and_timeouts(self):
        url = _scoped_url(
            "postgresql+psycopg2://u:p@host:5432/db?sslmode=require",
            "alembic_ci_abc123",
        )
        params = dict(url.query)
        assert params["connect_timeout"] == "10"
        options = params["options"]
        assert "search_path=alembic_ci_abc123" in options
        assert "statement_timeout=60000" in options
        assert "lock_timeout=5000" in options
        # Session shows up cleanly in pg_stat_activity, scoped to the schema.
        assert params["application_name"] == "equiped_migration_alembic_ci_abc123"
        # Existing query params (e.g. sslmode) are preserved.
        assert params["sslmode"] == "require"

    def test_cfg_round_trips_percent_encoded_scoped_url(self):
        url = _scoped_url(
            "postgresql+psycopg2://u:p@host:5432/db",
            "alembic_ci_abc123",
        )
        rendered = url.render_as_string(hide_password=False)
        cfg = _cfg(rendered)
        assert cfg.get_main_option("sqlalchemy.url") == rendered

    def test_generated_schema_guard_rejects_public(self):
        with pytest.raises(AssertionError, match="non-generated schema"):
            _assert_generated_schema("public")

    def test_generated_schema_guard_rejects_unvalidated(self):
        for name in (
            "",
            "alembic_ci_",
            "alembic_ci_XYZ",
            "alembic_ci_abc123_extra",
            "other_schema",
        ):
            with pytest.raises(AssertionError, match="non-generated schema"):
                _assert_generated_schema(name)

    def test_generated_schema_guard_accepts_generated(self):
        _assert_generated_schema("alembic_ci_abc123def456")

    def test_raw_head_check_accepts_exact_heads(self):
        _check_heads({BRANCH_A, BRANCH_B}, {BRANCH_A, BRANCH_B}, "collapse merge")

    def test_raw_head_check_rejects_mismatch(self):
        with pytest.raises(AssertionError, match="expected version heads"):
            _check_heads({BRANCH_A}, {BRANCH_A, BRANCH_B}, "collapse merge")
