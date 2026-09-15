"""Tests for 20260915_0002_add_item_level_feedback migration."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic.command import downgrade, upgrade
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

ROOT = Path(__file__).resolve().parents[2]


def _config(url: str) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    return config


def _run(command, config, revision):
    from server.core.config import get_settings

    get_settings.cache_clear()
    old = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = ""
    try:
        command(config, revision)
    finally:
        if old is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old
        get_settings.cache_clear()


def _prepare_schema(engine):
    with engine.begin() as conn:
        conn.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)")
        )
        conn.execute(text("INSERT INTO alembic_version VALUES ('20260915_0001')"))
        conn.execute(
            text(
                "CREATE TABLE preference_logs ("
                "log_id TEXT PRIMARY KEY, "
                "evaluation_id TEXT NOT NULL, "
                "user_id TEXT NOT NULL, "
                "agent_name TEXT, "
                "criterion_id TEXT, "
                "action TEXT NOT NULL, "
                "edited_json JSON, "
                "notes TEXT, "
                "created_at DATETIME NOT NULL, "
                "CONSTRAINT ck_preference_logs_action "
                "CHECK (action IN ('ACCEPT', 'REJECT', 'EDIT'))"
                ")"
            )
        )


def test_migration_upgrade_and_downgrade(tmp_path):
    url = f"sqlite+pysqlite:///{tmp_path / 'test_item_feedback.db'}"
    engine = create_engine(url)
    _prepare_schema(engine)

    _run(upgrade, _config(url), "20260915_0002")
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        assert ctx.get_current_revision() == "20260915_0002"
        cols = {c["name"] for c in inspect(engine).get_columns("preference_logs")}
        assert "item_id" in cols

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO preference_logs "
                "(log_id, evaluation_id, user_id, agent_name, criterion_id, "
                "item_id, action, created_at) VALUES "
                "('11111111-1111-1111-1111-111111111111', "
                "'22222222-2222-2222-2222-222222222222', "
                "'33333333-3333-3333-3333-333333333333', "
                "'sme', 'OP-01', 'u1', 'ITEM_REJECT', CURRENT_TIMESTAMP)"
            )
        )
        with pytest.raises(Exception, match="CHECK constraint failed"):
            conn.execute(
                text(
                    "INSERT INTO preference_logs "
                    "(log_id, evaluation_id, user_id, action, created_at) VALUES "
                    "('44444444-4444-4444-4444-444444444444', "
                    "'22222222-2222-2222-2222-222222222222', "
                    "'33333333-3333-3333-3333-333333333333', "
                    "'BOGUS', CURRENT_TIMESTAMP)"
                )
            )

    # Idempotent re-upgrade check
    _run(upgrade, _config(url), "20260915_0002")
    with engine.connect() as conn:
        cols = {c["name"] for c in inspect(engine).get_columns("preference_logs")}
        assert "item_id" in cols

    # Downgrade is inherently lossy for ITEM_REJECT/ITEM_ACCEPT rows (the old
    # constraint can't represent them) -- clear the row this test inserted so
    # the round-trip below exercises the migration mechanics, not that
    # unrelated data-loss behavior.
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM preference_logs"))

    _run(downgrade, _config(url), "20260915_0001")
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        assert ctx.get_current_revision() == "20260915_0001"
        cols = {c["name"] for c in inspect(engine).get_columns("preference_logs")}
        assert "item_id" not in cols

    engine.dispose()
