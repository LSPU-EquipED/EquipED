"""Tests for 20260820_0002_add_agent_result_group_responses migration."""

from __future__ import annotations

import os
from pathlib import Path

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


def test_migration_upgrade_and_downgrade(tmp_path):
    url = f"sqlite+pysqlite:///{tmp_path / 'test_group_responses.db'}"
    engine = create_engine(url)

    # Prepare schema up to 20260820_0001
    with engine.begin() as conn:
        conn.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)")
        )
        conn.execute(text("INSERT INTO alembic_version VALUES ('20260820_0001')"))
        conn.execute(
            text(
                "CREATE TABLE agent_results ("
                "agent_result_id TEXT PRIMARY KEY, "
                "evaluation_id TEXT NOT NULL, "
                "document_id TEXT NOT NULL, "
                "agent_name TEXT NOT NULL, "
                "prompt_version_id TEXT, "
                "subtotal REAL NOT NULL, "
                "processing_seconds REAL NOT NULL, "
                "token_count INTEGER NOT NULL, "
                "model_name TEXT NOT NULL, "
                "summary TEXT NOT NULL, "
                "success BOOLEAN NOT NULL, "
                "error_message TEXT, "
                "raw_response TEXT, "
                "prompt_text TEXT, "
                "group_prompts JSON, "
                "provenance JSON, "
                "advisory_outputs JSON, "
                "created_at DATETIME NOT NULL"
                ")"
            )
        )

    # Upgrade to 20260820_0002
    _run(upgrade, _config(url), "20260820_0002")
    with engine.connect() as conn:
        assert (
            MigrationContext.configure(conn).get_current_revision()
            == "20260820_0002"
        )
        cols = {c["name"] for c in inspect(engine).get_columns("agent_results")}
        assert "group_responses" in cols

    # Idempotent re-upgrade check
    _run(upgrade, _config(url), "20260820_0002")
    with engine.connect() as conn:
        cols = {c["name"] for c in inspect(engine).get_columns("agent_results")}
        assert "group_responses" in cols

    # Downgrade back to 20260820_0001
    _run(downgrade, _config(url), "20260820_0001")
    with engine.connect() as conn:
        assert (
            MigrationContext.configure(conn).get_current_revision()
            == "20260820_0001"
        )
        cols = {c["name"] for c in inspect(engine).get_columns("agent_results")}
        assert "group_responses" not in cols

    engine.dispose()
