"""Tests for 20260918_0003_enforce_unique_adapter_version migration."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
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


def _setup_test_database(engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)")
        )
        conn.execute(text("INSERT INTO alembic_version VALUES ('20260918_0002')"))

        conn.execute(
            text(
                "CREATE TABLE dpo_training_jobs ("
                "job_id CHAR(36) PRIMARY KEY, "
                "agent_id VARCHAR(32) NOT NULL"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE trained_adapters ("
                "adapter_id CHAR(36) PRIMARY KEY, "
                "agent_id VARCHAR(32) NOT NULL, "
                "job_id CHAR(36) REFERENCES dpo_training_jobs(job_id), "
                "version INTEGER NOT NULL, "
                "file_path VARCHAR(512) NOT NULL, "
                "file_sha256 VARCHAR(64) NOT NULL, "
                "size_bytes INTEGER NOT NULL, "
                "created_at DATETIME NOT NULL"
                ")"
            )
        )


def test_upgrade_renumbers_duplicate_versions_and_downgrade_drops_index(tmp_path):
    """Safely handle pre-existing duplicates by renumbering per agent_id in stable
    order, preserving all rows, then applying unique index; verify downgrade drops
    the index."""
    db_path = tmp_path / "test_migration_0003_duplicates.db"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)

    _setup_test_database(engine)

    insert_sql = (
        "INSERT INTO trained_adapters (adapter_id, agent_id, job_id, version, "
        "file_path, file_sha256, size_bytes, created_at) "
        "VALUES (:aid, :gid, :jid, :ver, :fp, :sha, :sz, :created_at)"
    )

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO dpo_training_jobs (job_id, agent_id) VALUES ('j1', 'gad')"
            )
        )
        # Pre-existing duplicate versions for gad: two version 1s, one version 2
        # created_at:
        # gad row 1: '2026-09-01 10:00:00', adapter_id: 'b-gad-1', version: 1
        # gad row 2: '2026-09-01 10:00:00', adapter_id: 'a-gad-2', version: 1
        #   (tie in created_at, adapter_id 'a-gad-2' < 'b-gad-1')
        # gad row 3: '2026-09-02 10:00:00', adapter_id: 'c-gad-3', version: 2
        # SME rows with duplicates:
        # sme row 1: '2026-09-01 11:00:00', adapter_id: 'sme-1', version: 5
        # sme row 2: '2026-09-02 11:00:00', adapter_id: 'sme-2', version: 5
        conn.execute(
            text(insert_sql),
            [
                {
                    "aid": "b-gad-1",
                    "gid": "gad",
                    "jid": "j1",
                    "ver": 1,
                    "fp": "/p1",
                    "sha": "s1",
                    "sz": 10,
                    "created_at": "2026-09-01 10:00:00",
                },
                {
                    "aid": "a-gad-2",
                    "gid": "gad",
                    "jid": "j1",
                    "ver": 1,
                    "fp": "/p2",
                    "sha": "s2",
                    "sz": 20,
                    "created_at": "2026-09-01 10:00:00",
                },
                {
                    "aid": "c-gad-3",
                    "gid": "gad",
                    "jid": "j1",
                    "ver": 2,
                    "fp": "/p3",
                    "sha": "s3",
                    "sz": 30,
                    "created_at": "2026-09-02 10:00:00",
                },
                {
                    "aid": "sme-1",
                    "gid": "sme",
                    "jid": "j1",
                    "ver": 5,
                    "fp": "/p4",
                    "sha": "s4",
                    "sz": 40,
                    "created_at": "2026-09-01 11:00:00",
                },
                {
                    "aid": "sme-2",
                    "gid": "sme",
                    "jid": "j1",
                    "ver": 5,
                    "fp": "/p5",
                    "sha": "s5",
                    "sz": 50,
                    "created_at": "2026-09-02 11:00:00",
                },
            ],
        )

    # Run upgrade - should not fail despite pre-existing duplicates!
    _run_migration(alembic_upgrade, db_url, "20260918_0003")

    with engine.connect() as conn:
        gad_rows = (
            conn.execute(
                text(
                    "SELECT adapter_id, version FROM trained_adapters "
                    "WHERE agent_id = 'gad' ORDER BY version"
                )
            )
            .mappings()
            .all()
        )
        assert len(gad_rows) == 3
        # Stable order: created_at ASC, adapter_id ASC
        # 1. a-gad-2 (2026-09-01, id: a-gad-2) -> version 1
        # 2. b-gad-1 (2026-09-01, id: b-gad-1) -> version 2
        # 3. c-gad-3 (2026-09-02, id: c-gad-3) -> version 3
        assert gad_rows[0]["adapter_id"] == "a-gad-2"
        assert gad_rows[0]["version"] == 1
        assert gad_rows[1]["adapter_id"] == "b-gad-1"
        assert gad_rows[1]["version"] == 2
        assert gad_rows[2]["adapter_id"] == "c-gad-3"
        assert gad_rows[2]["version"] == 3

        sme_rows = (
            conn.execute(
                text(
                    "SELECT adapter_id, version FROM trained_adapters "
                    "WHERE agent_id = 'sme' ORDER BY version"
                )
            )
            .mappings()
            .all()
        )
        assert len(sme_rows) == 2
        assert sme_rows[0]["adapter_id"] == "sme-1"
        assert sme_rows[0]["version"] == 1
        assert sme_rows[1]["adapter_id"] == "sme-2"
        assert sme_rows[1]["version"] == 2

    # Unique index exists
    inspector = inspect(engine)
    indexes = {i["name"]: i for i in inspector.get_indexes("trained_adapters")}
    assert "uq_trained_adapters_agent_version" in indexes
    assert indexes["uq_trained_adapters_agent_version"]["unique"]

    # Run downgrade
    _run_migration(alembic_downgrade, db_url, "20260918_0002")

    inspector = inspect(engine)
    indexes = [i["name"] for i in inspector.get_indexes("trained_adapters")]
    assert "uq_trained_adapters_agent_version" not in indexes

    # Verify rows preserved after downgrade
    with engine.connect() as conn:
        total = conn.execute(text("SELECT count(*) FROM trained_adapters")).scalar()
        assert total == 5


def test_upgrade_creates_unique_index_and_downgrade_drops(tmp_path):
    db_path = tmp_path / "test_migration_0003.db"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)

    _setup_test_database(engine)

    # Verify unique index does not exist before migration
    inspector = inspect(engine)
    indexes = [i["name"] for i in inspector.get_indexes("trained_adapters")]
    assert "uq_trained_adapters_agent_version" not in indexes

    # Run upgrade
    _run_migration(alembic_upgrade, db_url, "20260918_0003")

    inspector = inspect(engine)
    indexes = {i["name"]: i for i in inspector.get_indexes("trained_adapters")}
    assert "uq_trained_adapters_agent_version" in indexes
    assert indexes["uq_trained_adapters_agent_version"]["unique"]
    assert indexes["uq_trained_adapters_agent_version"]["column_names"] == [
        "agent_id",
        "version",
    ]

    # Verify duplicate insertion fails under the unique index
    insert_sql = (
        "INSERT INTO trained_adapters (adapter_id, agent_id, job_id, version, "
        "file_path, file_sha256, size_bytes, created_at) "
        "VALUES (:aid, :gid, :jid, :ver, :fp, :sha, :sz, '2026-09-18 00:00:00')"
    )
    with engine.begin() as conn:
        conn.execute(
            text(insert_sql),
            {
                "aid": "a1",
                "gid": "gad",
                "jid": "j1",
                "ver": 1,
                "fp": "/p1",
                "sha": "s1",
                "sz": 10,
            },
        )
    with pytest.raises(Exception):
        with engine.begin() as conn:
            conn.execute(
                text(insert_sql),
                {
                    "aid": "a2",
                    "gid": "gad",
                    "jid": "j2",
                    "ver": 1,
                    "fp": "/p2",
                    "sha": "s2",
                    "sz": 10,
                },
            )

    # Different agent with same version should succeed
    with engine.begin() as conn:
        conn.execute(
            text(insert_sql),
            {
                "aid": "a3",
                "gid": "sme",
                "jid": "j1",
                "ver": 1,
                "fp": "/p3",
                "sha": "s3",
                "sz": 10,
            },
        )

    # Run downgrade
    _run_migration(alembic_downgrade, db_url, "20260918_0002")

    inspector = inspect(engine)
    indexes = [i["name"] for i in inspector.get_indexes("trained_adapters")]
    assert "uq_trained_adapters_agent_version" not in indexes
