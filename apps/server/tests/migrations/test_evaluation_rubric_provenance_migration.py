from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic.command import downgrade, upgrade
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

ROOT = Path(__file__).resolve().parents[2]
REV = "20261011_0001"
DOWN = "20261010_0002"


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


def _seed_schema(conn) -> None:
    conn.execute(
        text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)")
    )
    conn.execute(
        text("INSERT INTO alembic_version VALUES (:revision)"), {"revision": DOWN}
    )
    conn.execute(
        text(
            "CREATE TABLE rubric_sets ("
            "rubric_set_id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, "
            "name TEXT NOT NULL, version_number INTEGER NOT NULL, "
            "adapter_key TEXT NOT NULL, adapter_version INTEGER NOT NULL, "
            "retired_at DATETIME, "
            "CONSTRAINT uq_rubric_sets_agent_version UNIQUE (agent_id, version_number))"
        )
    )
    conn.execute(
        text(
            "CREATE TABLE evaluation_form_snapshots ("
            "snapshot_id TEXT PRIMARY KEY, evaluation_id TEXT NOT NULL, "
            "agent_id TEXT NOT NULL, rubric_set_id TEXT NOT NULL, "
            "snapshot_payload JSON NOT NULL, snapshot_hash TEXT NOT NULL, "
            "adapter_key TEXT NOT NULL, adapter_version INTEGER NOT NULL, "
            "created_at DATETIME NOT NULL, "
            "CONSTRAINT fk_eval_snapshots_rubric_set_id "
            "FOREIGN KEY (rubric_set_id) REFERENCES rubric_sets (rubric_set_id))"
        )
    )
    conn.execute(
        text(
            "INSERT INTO rubric_sets VALUES "
            "('coord-set','coordinator','Coordinator v1',1,'coordinator',1,NULL),"
            "('sme-set','sme','SME v1',1,'sme',1,NULL)"
        )
    )
    conn.execute(
        text(
            "INSERT INTO evaluation_form_snapshots VALUES "
            "('coord-snapshot','evaluation-1','coordinator','coord-set',"
            "'{\"form\": {}}','coord-hash','coordinator',1,'2026-01-01'),"
            "('sme-snapshot','evaluation-2','sme','sme-set',"
            "'{\"form\": {}}','sme-hash','sme',1,'2026-01-01')"
        )
    )


def test_downgrade_refuses_to_delete_orphaned_provenance(tmp_path):
    url = f"sqlite+pysqlite:///{tmp_path / 'provenance_refusal.db'}"
    engine = create_engine(url)
    with engine.begin() as conn:
        _seed_schema(conn)
    _run(upgrade, _config(url), REV)

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM rubric_sets WHERE rubric_set_id = 'coord-set'"))

    try:
        _run(downgrade, _config(url), DOWN)
    except RuntimeError as exc:
        assert "restore every referenced" in str(exc)
    else:
        pytest.fail("downgrade must refuse to delete orphaned provenance")

    with engine.connect() as conn:
        assert "evaluation_rubric_provenance" in inspect(conn).get_table_names()
    engine.dispose()


def test_upgrade_backfills_all_agents_and_repoints_snapshot_fk(tmp_path):
    url = f"sqlite+pysqlite:///{tmp_path / 'provenance.db'}"
    engine = create_engine(url)
    with engine.begin() as conn:
        _seed_schema(conn)

    _run(upgrade, _config(url), REV)

    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT rubric_set_id, agent_id, version_number, name, adapter_key, "
                "adapter_version FROM evaluation_rubric_provenance "
                "ORDER BY agent_id"
            )
        ).all()
        assert [tuple(row) for row in rows] == [
            ("coord-set", "coordinator", 1, "Coordinator v1", "coordinator", 1),
            ("sme-set", "sme", 1, "SME v1", "sme", 1),
        ]
        fks = inspect(conn).get_foreign_keys("evaluation_form_snapshots")
        assert (
            "evaluation_rubric_provenance",
            ("rubric_set_id",),
            ("rubric_set_id",),
        ) in {
            (
                fk["referred_table"],
                tuple(fk["constrained_columns"]),
                tuple(fk["referred_columns"]),
            )
            for fk in fks
        }

    _run(downgrade, _config(url), DOWN)
    with engine.connect() as conn:
        assert "evaluation_rubric_provenance" not in inspect(conn).get_table_names()
        fks = inspect(conn).get_foreign_keys("evaluation_form_snapshots")
        assert ("rubric_sets", ("rubric_set_id",), ("rubric_set_id",)) in {
            (
                fk["referred_table"],
                tuple(fk["constrained_columns"]),
                tuple(fk["referred_columns"]),
            )
            for fk in fks
        }
    engine.dispose()
