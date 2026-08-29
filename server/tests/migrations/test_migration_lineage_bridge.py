"""Verify the restored externally applied migration lineage."""

from __future__ import annotations

import os
from pathlib import Path

from alembic.command import downgrade, upgrade
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

ROOT = Path(__file__).resolve().parents[3]


def _config(url: str) -> Config:
    config = Config(str(ROOT / "server" / "alembic.ini"))
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


def test_bridge_is_noop_and_admission_path_is_clean(tmp_path):
    url = f"sqlite+pysqlite:///{tmp_path / 'lineage.db'}"
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)")
        )
        conn.execute(text("INSERT INTO alembic_version VALUES ('20260808_0002')"))
        conn.execute(
            text(
                "CREATE TABLE evaluation_jobs (evaluation_id TEXT PRIMARY KEY, "
                "status TEXT NOT NULL, submitted_at TEXT NOT NULL)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE prompt_versions (version_id TEXT PRIMARY KEY, "
                "agent_id TEXT NOT NULL, version_number INTEGER NOT NULL, "
                "prompt_text TEXT NOT NULL, is_active BOOLEAN NOT NULL, "
                "motivation TEXT, created_at DATETIME NOT NULL, updated_by TEXT NULL, "
                "UNIQUE (agent_id, version_number))"
            )
        )
    _run(upgrade, _config(url), "20260810_0002")
    with engine.connect() as conn:
        assert (
            MigrationContext.configure(conn).get_current_revision() == "20260810_0002"
        )
    _run(upgrade, _config(url), "20260811_0002")
    with engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT COUNT(*) FROM prompt_versions WHERE agent_id='sme'")
            ).scalar_one()
            == 1
        )
        assert "admission_slot" in {
            c["name"] for c in inspect(engine).get_columns("evaluation_jobs")
        }
    _run(downgrade, _config(url), "20260810_0002")
    with engine.connect() as conn:
        assert (
            MigrationContext.configure(conn).get_current_revision() == "20260810_0002"
        )
    engine.dispose()


def test_history_contains_bridge_and_single_head():
    script = ScriptDirectory.from_config(_config("sqlite+pysqlite:///:memory:"))

    bridge = script.get_revision("20260810_0002")
    assert bridge is not None
    assert bridge.down_revision == "20260808_0002"
    assert script.get_heads() == ["20260829_0002"]
    # DPO feature migrations re-home off the current head after the bridge.
    assert script.get_revision("20260811_0003").down_revision == "20260811_0002"
    assert script.get_revision("20260811_0004").down_revision == "20260811_0003"
    assert script.get_revision("20260814_0001").down_revision == "20260811_0004"
    assert script.get_revision("20260820_0001").down_revision == "20260814_0001"
    assert script.get_revision("20260820_0002").down_revision == "20260820_0001"
    assert script.get_revision("20260829_0001").down_revision == "20260820_0002"
    assert script.get_revision("20260829_0002").down_revision == "20260829_0001"
