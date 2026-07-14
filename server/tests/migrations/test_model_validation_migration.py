"""Offline SQLite migration tests for 20260714_0001.

Tests both fresh-DB and legacy-DB (pre-existing tables from old
fragmented migrations) upgrade paths, plus downgrade safety.
Uses Alembic's ``alembic.command`` API for proper context setup.
"""

from __future__ import annotations

import io
import os
import re
import sys
from pathlib import Path

import pytest
from alembic.command import downgrade as alembic_downgrade
from alembic.command import upgrade as alembic_upgrade
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

# Ensure repo root is on sys.path so Alembic's env.py can import server modules.
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

REVISION = "20260714_0001"
BASE_REV = "20260713_0005"


def _cfg(db_url: str) -> Config:
    """Return an Alembic Config for the given database URL."""
    ini = str(REPO_ROOT / "server" / "alembic.ini")
    c = Config(ini)
    c.set_main_option("sqlalchemy.url", db_url)
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


def _create_legacy_tables(engine) -> None:
    """Create tables as they would exist after old 0001+0002+0003.

    Uses raw CREATE TABLE strings to avoid SQLAlchemy Column/Type
    positional confusion across versions.
    """
    from sqlalchemy import text as sql_text

    with engine.begin() as conn:
        conn.execute(sql_text("CREATE TABLE users (user_id TEXT PRIMARY KEY)"))
        conn.execute(
            sql_text(
                "CREATE TABLE evaluation_jobs "
                "(evaluation_id TEXT PRIMARY KEY)"
            )
        )
        conn.execute(sql_text("""
            CREATE TABLE model_validations (
                validation_id TEXT PRIMARY KEY,
                evaluation_id TEXT NOT NULL UNIQUE,
                toxicity_score TEXT,
                toxicity_label TEXT,
                toxicity_explanation TEXT,
                toxicity_model TEXT,
                toxicity_error TEXT,
                toxicity_assessed_at TEXT,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """))
        conn.execute(sql_text("""
            CREATE TABLE model_validation_criterion_scores (
                expected_score_id TEXT PRIMARY KEY,
                validation_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                criterion_id TEXT NOT NULL,
                criterion_title TEXT NOT NULL,
                expected_score TEXT NOT NULL,
                actual_score TEXT,
                absolute_error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """))


def _create_legacy_tables_with_forbidden_column(engine) -> None:
    """Simulate legacy state where expected_score was never dropped."""
    from sqlalchemy import text as sql_text

    with engine.begin() as conn:
        conn.execute(sql_text("CREATE TABLE users (user_id TEXT PRIMARY KEY)"))
        conn.execute(
            sql_text(
                "CREATE TABLE evaluation_jobs "
                "(evaluation_id TEXT PRIMARY KEY)"
            )
        )
        conn.execute(sql_text("""
            CREATE TABLE model_validations (
                validation_id TEXT PRIMARY KEY,
                evaluation_id TEXT NOT NULL UNIQUE,
                expected_score TEXT NOT NULL,
                toxicity_score TEXT,
                toxicity_label TEXT,
                toxicity_explanation TEXT,
                toxicity_model TEXT,
                toxicity_error TEXT,
                toxicity_assessed_at TEXT,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """))


# ═══════════════════════════════════════════════════════════════════════
# Chain structure tests
# ═══════════════════════════════════════════════════════════════════════


class TestChainStructure:
    """The migration chain is linear and includes the new revision."""

    def test_single_head(self):
        script = ScriptDirectory.from_config(_cfg("sqlite://"))
        heads = script.get_heads()
        assert len(heads) == 1, f"Expected 1 head, got {len(heads)}: {heads}"

    def test_revision_in_chain(self):
        script = ScriptDirectory.from_config(_cfg("sqlite://"))
        head = script.get_heads()[0]
        rev = script.get_revision(head)
        seen: list[str] = []
        while rev is not None:
            seen.append(rev.revision)
            down = rev.down_revision
            if isinstance(down, str):
                rev = script.get_revision(down) if down else None
            else:
                rev = None
        assert REVISION in seen, f"{REVISION} not found in chain: {seen}"

    def test_base_revision_is_parent(self):
        script = ScriptDirectory.from_config(_cfg("sqlite://"))
        rev_obj = script.get_revision(REVISION)
        assert rev_obj is not None
        assert rev_obj.down_revision == BASE_REV


# ═══════════════════════════════════════════════════════════════════════
# Offline SQL verification (no database)
# ═══════════════════════════════════════════════════════════════════════


def _run_offline(cfg: Config, revision_range: str) -> str:
    """Run *revision_range* in offline (--sql) mode, return generated SQL."""
    import io

    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        alembic_upgrade(cfg, revision_range, sql=True)
    finally:
        sys.stdout = old
    return buf.getvalue()


class TestOfflineSQL:
    """Generated DDL is correct for both paths."""

    def test_fresh_offline_creates_both_tables(self):
        sql = _run_offline(
            _cfg("sqlite://"), f"{BASE_REV}:{REVISION}"
        )
        assert "CREATE TABLE model_validations" in sql
        assert "CREATE TABLE model_validation_criterion_scores" in sql
        assert "idx_model_validations_created_by" in sql
        assert "idx_validation_criterion_validation" in sql
        assert "uq_model_validations_evaluation" in sql
        assert "uq_validation_agent_criterion" in sql
        # expected_score must not appear in model_validations columns
        mv_create_match = re.search(
            r"CREATE TABLE model_validations \((.*?)\);", sql, re.DOTALL
        )
        assert mv_create_match is not None
        assert "expected_score" not in mv_create_match.group(1)

    def test_fresh_downgrade_offline(self):
        """Offline SQL for downgrade drops both tables."""
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            alembic_downgrade(
                _cfg("postgresql://ignored"),
                f"{REVISION}:{BASE_REV}",
                sql=True,
            )
        finally:
            sys.stdout = old
        sql = buf.getvalue()
        assert "DROP TABLE model_validation_criterion_scores" in sql
        assert "DROP TABLE model_validations" in sql


# ═══════════════════════════════════════════════════════════════════════
# Fresh-DB online upgrade
# ═══════════════════════════════════════════════════════════════════════


class TestFreshUpgrade:
    """Upgrade creates both tables when they don't exist."""

    def test_creates_both_tables(self, tmp_path):
        db = tmp_path / "fresh.db"
        db_url = f"sqlite+pysqlite:///{db}"
        engine = create_engine(db_url)
        _stamp(engine, BASE_REV)
        engine.dispose()

        engine = create_engine(db_url)
        _upgrade_online(_cfg(db_url), REVISION)

        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "model_validations" in tables
        assert "model_validation_criterion_scores" in tables

        mv_cols = {c["name"] for c in inspector.get_columns("model_validations")}
        assert "expected_score" not in mv_cols
        for required in (
            "validation_id",
            "evaluation_id",
            "toxicity_score",
            "toxicity_label",
            "toxicity_explanation",
            "toxicity_model",
            "toxicity_error",
            "toxicity_assessed_at",
            "created_by",
            "created_at",
        ):
            assert required in mv_cols, f"Missing column {required}"

        crit_cols = {
            c["name"]
            for c in inspector.get_columns("model_validation_criterion_scores")
        }
        for required in (
            "expected_score_id",
            "validation_id",
            "agent_id",
            "criterion_id",
            "criterion_title",
            "expected_score",
            "actual_score",
            "absolute_error",
            "created_at",
            "updated_at",
        ):
            assert required in crit_cols, f"Missing column {required}"

        engine.dispose()

    def test_creates_indexes(self, tmp_path):
        db = tmp_path / "fresh_idx.db"
        db_url = f"sqlite+pysqlite:///{db}"
        engine = create_engine(db_url)
        _stamp(engine, BASE_REV)
        engine.dispose()

        engine = create_engine(db_url)
        _upgrade_online(_cfg(db_url), REVISION)

        inspector = inspect(engine)
        mv_ix = {ix["name"] for ix in inspector.get_indexes("model_validations")}
        assert "idx_model_validations_created_by" in mv_ix
        assert "uq_model_validations_evaluation" in mv_ix

        crit_ix = {
            ix["name"]
            for ix in inspector.get_indexes("model_validation_criterion_scores")
        }
        assert "idx_validation_criterion_validation" in crit_ix
        assert "uq_validation_agent_criterion" in crit_ix

        engine.dispose()

    def test_current_updates_to_revision(self, tmp_path):
        db = tmp_path / "fresh_cur.db"
        db_url = f"sqlite+pysqlite:///{db}"
        engine = create_engine(db_url)
        _stamp(engine, BASE_REV)
        engine.dispose()

        engine = create_engine(db_url)
        _upgrade_online(_cfg(db_url), REVISION)
        cur = _current(engine)
        assert cur == REVISION, f"Expected current={REVISION}, got {cur}"
        engine.dispose()


# ═══════════════════════════════════════════════════════════════════════
# Fresh-DB downgrade
# ═══════════════════════════════════════════════════════════════════════


class TestFreshDowngrade:
    """Downgrade drops both tables when they were created by this migration."""

    def test_downgrade_drops_both_tables(self, tmp_path):
        db = tmp_path / "fresh_down.db"
        db_url = f"sqlite+pysqlite:///{db}"
        engine = create_engine(db_url)
        _stamp(engine, BASE_REV)
        engine.dispose()

        engine = create_engine(db_url)
        _upgrade_online(_cfg(db_url), REVISION)
        cur = _current(engine)
        assert cur == REVISION

        _downgrade_online(_cfg(db_url), BASE_REV)
        cur = _current(engine)
        assert cur == BASE_REV

        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "model_validations" not in tables
        assert "model_validation_criterion_scores" not in tables
        engine.dispose()


# ═══════════════════════════════════════════════════════════════════════
# Legacy-DB upgrade (tables already exist)
# ═══════════════════════════════════════════════════════════════════════


class TestLegacyUpgrade:
    """Upgrade is safe when tables already exist from old migrations."""

    def test_legacy_upgrade_is_safe(self, tmp_path):
        db = tmp_path / "legacy.db"
        db_url = f"sqlite+pysqlite:///{db}"
        engine = create_engine(db_url)
        _create_legacy_tables(engine)
        _stamp(engine, BASE_REV)
        engine.dispose()

        engine = create_engine(db_url)
        _upgrade_online(_cfg(db_url), REVISION)

        cur = _current(engine)
        assert cur == REVISION

        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "model_validations" in tables
        assert "model_validation_criterion_scores" in tables
        engine.dispose()

    def test_legacy_upgrade_adds_missing_indexes(self, tmp_path):
        db = tmp_path / "legacy_idx.db"
        db_url = f"sqlite+pysqlite:///{db}"
        engine = create_engine(db_url)
        _create_legacy_tables(engine)
        _stamp(engine, BASE_REV)
        engine.dispose()

        engine = create_engine(db_url)
        _upgrade_online(_cfg(db_url), REVISION)

        inspector = inspect(engine)
        mv_ix = {ix["name"] for ix in inspector.get_indexes("model_validations")}
        assert "idx_model_validations_created_by" in mv_ix
        assert "uq_model_validations_evaluation" in mv_ix

        crit_ix = {
            ix["name"]
            for ix in inspector.get_indexes("model_validation_criterion_scores")
        }
        assert "idx_validation_criterion_validation" in crit_ix
        assert "uq_validation_agent_criterion" in crit_ix
        engine.dispose()

    def test_legacy_upgrade_fails_on_incompatible_column(self, tmp_path):
        db = tmp_path / "legacy_bad.db"
        db_url = f"sqlite+pysqlite:///{db}"
        engine = create_engine(db_url)
        _create_legacy_tables_with_forbidden_column(engine)
        _stamp(engine, BASE_REV)
        engine.dispose()

        engine = create_engine(db_url)
        with pytest.raises(Exception, match="expected_score"):
            _upgrade_online(_cfg(db_url), REVISION)
        engine.dispose()

    def test_legacy_upgrade_creates_missing_criterion_table(self, tmp_path):
        db = tmp_path / "legacy_partial.db"
        db_url = f"sqlite+pysqlite:///{db}"
        engine = create_engine(db_url)
        # Only create model_validations, not the criterion table
        from sqlalchemy import text as sql_text

        with engine.begin() as conn:
            conn.execute(
                sql_text("CREATE TABLE users (user_id TEXT PRIMARY KEY)")
            )
            conn.execute(
                sql_text(
                    "CREATE TABLE evaluation_jobs "
                    "(evaluation_id TEXT PRIMARY KEY)"
                )
            )
            conn.execute(sql_text("""
                CREATE TABLE model_validations (
                    validation_id TEXT PRIMARY KEY,
                    evaluation_id TEXT NOT NULL UNIQUE,
                    toxicity_score TEXT,
                    toxicity_label TEXT,
                    toxicity_explanation TEXT,
                    toxicity_model TEXT,
                    toxicity_error TEXT,
                    toxicity_assessed_at TEXT,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """))
        _stamp(engine, BASE_REV)
        engine.dispose()

        engine = create_engine(db_url)
        _upgrade_online(_cfg(db_url), REVISION)

        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "model_validation_criterion_scores" in tables
        engine.dispose()

    def test_legacy_downgrade_is_safe(self, tmp_path):
        """Downgrade on legacy DB does not raise — tables survive."""
        db = tmp_path / "legacy_down.db"
        db_url = f"sqlite+pysqlite:///{db}"
        engine = create_engine(db_url)
        _create_legacy_tables(engine)
        _stamp(engine, BASE_REV)
        engine.dispose()

        engine = create_engine(db_url)
        _upgrade_online(_cfg(db_url), REVISION)
        assert _current(engine) == REVISION

        _downgrade_online(_cfg(db_url), BASE_REV)
        cur = _current(engine)
        assert cur == BASE_REV

        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "model_validations" in tables
        assert "model_validation_criterion_scores" in tables
        engine.dispose()
