"""Tests for 20260929_0001_add_agent_adapter_publication migration."""

from __future__ import annotations

import os
from pathlib import Path

from alembic.command import downgrade as alembic_downgrade
from alembic.command import upgrade as alembic_upgrade
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

REPO_ROOT = Path(__file__).resolve().parents[2]


def _config(database_url: str) -> Config:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _run_migration(command, database_url: str, revision: str) -> None:
    from server.core.config import get_settings

    config = _config(database_url)
    original = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = ""
    get_settings.cache_clear()
    try:
        command(config, revision)
    finally:
        if original is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original
        get_settings.cache_clear()


def _setup(engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)")
        )
        conn.execute(text("INSERT INTO alembic_version VALUES ('20260923_0001')"))
        conn.execute(text("CREATE TABLE users (user_id CHAR(36) PRIMARY KEY)"))
        conn.execute(
            text("CREATE TABLE trained_adapters (adapter_id CHAR(36) PRIMARY KEY)")
        )
        conn.execute(
            text("CREATE TABLE evaluation_jobs (evaluation_id CHAR(36) PRIMARY KEY)")
        )
        conn.execute(
            text(
                "CREATE TABLE model_validations ("
                "validation_id CHAR(36) PRIMARY KEY, "
                "evaluation_id CHAR(36) NOT NULL)"
            )
        )


def test_upgrade_creates_table_and_columns_and_downgrade_removes_them(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'pub.db'}"
    engine = create_engine(db_url)
    _setup(engine)

    _run_migration(alembic_upgrade, db_url, "20260929_0001")

    inspector = inspect(engine)
    assert "agent_adapter_publication" in inspector.get_table_names()
    pub_cols = {c["name"] for c in inspector.get_columns("agent_adapter_publication")}
    assert pub_cols == {"agent_id", "adapter_id", "published_by", "published_at"}
    job_cols = {c["name"] for c in inspector.get_columns("evaluation_jobs")}
    assert {"adapter_request", "adapter_resolution"} <= job_cols
    val_cols = {c["name"] for c in inspector.get_columns("model_validations")}
    assert "adapter_id" in val_cols

    _run_migration(alembic_downgrade, db_url, "20260923_0001")

    inspector = inspect(engine)
    assert "agent_adapter_publication" not in inspector.get_table_names()
    assert "adapter_request" not in {
        c["name"] for c in inspector.get_columns("evaluation_jobs")
    }
    assert "adapter_id" not in {
        c["name"] for c in inspector.get_columns("model_validations")
    }
