"""Tests for 20260915_0003_add_agent_generations migration."""

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


def _prepare_schema(engine):
    with engine.begin() as conn:
        conn.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)")
        )
        conn.execute(text("INSERT INTO alembic_version VALUES ('20260915_0002')"))
        conn.execute(
            text(
                "CREATE TABLE agent_results ("
                "agent_result_id TEXT PRIMARY KEY, "
                "evaluation_id TEXT NOT NULL, "
                "document_id TEXT NOT NULL, "
                "agent_name VARCHAR(50) NOT NULL"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE evaluation_form_snapshots ("
                "snapshot_id TEXT PRIMARY KEY, "
                "evaluation_id TEXT NOT NULL, "
                "agent_id VARCHAR(32) NOT NULL"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE preference_logs ("
                "log_id TEXT PRIMARY KEY, "
                "evaluation_id TEXT NOT NULL, "
                "user_id TEXT NOT NULL, "
                "agent_name TEXT, "
                "criterion_id TEXT, "
                "item_id TEXT, "
                "action TEXT NOT NULL, "
                "edited_json JSON, "
                "notes TEXT, "
                "created_at DATETIME NOT NULL"
                ")"
            )
        )


def test_agent_generations_migration_upgrade_and_downgrade(tmp_path):
    url = f"sqlite+pysqlite:///{tmp_path / 'test_generations_mig.db'}"
    engine = create_engine(url)
    _prepare_schema(engine)

    _run(upgrade, _config(url), "20260915_0003")
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        assert ctx.get_current_revision() == "20260915_0003"
        tables = inspect(engine).get_table_names()
        assert "agent_generations" in tables
        gen_cols = {c["name"] for c in inspect(engine).get_columns("agent_generations")}
        assert {
            "generation_id",
            "agent_result_id",
            "form_snapshot_id",
            "evaluation_id",
            "document_id",
            "agent_id",
            "unit_key",
            "criterion_ids",
            "prompt_text",
            "prompt_messages",
            "response_text",
            "response_json",
            "response_contract_key",
            "response_contract_version",
            "model_name",
            "prompt_version_id",
            "envelope_status",
            "generation_provenance",
            "prompt_sha256",
            "response_sha256",
            "capture_origin",
            "created_at",
        }.issubset(gen_cols)

        pref_cols = {c["name"] for c in inspect(engine).get_columns("preference_logs")}
        assert "generation_id" in pref_cols

    # Test idempotence of upgrade
    _run(upgrade, _config(url), "20260915_0003")
    with engine.connect() as conn:
        tables = inspect(engine).get_table_names()
        assert "agent_generations" in tables

    # Test downgrade to 20260915_0002
    _run(downgrade, _config(url), "20260915_0002")
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        assert ctx.get_current_revision() == "20260915_0002"
        tables = inspect(engine).get_table_names()
        assert "agent_generations" not in tables
        pref_cols = {c["name"] for c in inspect(engine).get_columns("preference_logs")}
        assert "generation_id" not in pref_cols

    engine.dispose()
