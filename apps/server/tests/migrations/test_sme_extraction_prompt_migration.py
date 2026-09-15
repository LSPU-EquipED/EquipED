"""Verify the SME prompt seed against the production prompt schema shape."""

from __future__ import annotations

import importlib

import pytest
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, text

BASE, HEAD = "20260811_0001", "20260811_0002"
SEEDED_ID = "b1c2d3e4-f5a6-7890-abcd-ef1234567890"


def _run(migration, engine, operation):
    with engine.begin() as conn:
        context = MigrationContext.configure(conn)
        with Operations.context(context):
            operation()


def _engine(tmp_path, rows):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'sme.db'}")
    with engine.begin() as conn:
        conn.execute(
            text("""CREATE TABLE prompt_versions (
            version_id TEXT PRIMARY KEY, agent_id TEXT NOT NULL,
            version_number INTEGER NOT NULL, prompt_text TEXT NOT NULL,
            is_active BOOLEAN NOT NULL, motivation TEXT,
            created_at DATETIME NOT NULL, updated_by TEXT NULL,
            CONSTRAINT uq_prompt_versions_agent_version
                UNIQUE (agent_id, version_number)
        )""")
        )
        conn.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)")
        )
        conn.execute(
            text("INSERT INTO alembic_version VALUES (:revision)"), {"revision": BASE}
        )
        for version_id, agent, number, active in rows:
            conn.execute(
                text("""INSERT INTO prompt_versions
                    (version_id, agent_id, version_number, prompt_text,
                     is_active, motivation, created_at, updated_by)
                    VALUES (:id, :agent, :number, 'prompt', :active,
                            'test', '2026-01-01', NULL)"""),
                {"id": version_id, "agent": agent, "number": number, "active": active},
            )
    return engine


def _active(conn, agent="sme"):
    return (
        conn.execute(
            text(
                "SELECT version_id, version_number FROM prompt_versions "
                "WHERE agent_id=:agent AND is_active=1 ORDER BY version_number"
            ),
            {"agent": agent},
        )
        .mappings()
        .all()
    )


@pytest.mark.parametrize(
    "existing, expected",
    [
        ([("sme-v1", "sme", 1, 0), ("sme-v2", "sme", 2, 1)], 3),
        (
            [("sme-v1", "sme", 1, 0), ("sme-v2", "sme", 2, 0), ("sme-v3", "sme", 3, 1)],
            4,
        ),
    ],
)
def test_upgrade_allocates_next_version_and_is_idempotent(tmp_path, existing, expected):
    engine = _engine(tmp_path, [*existing, ("gad-v1", "gad", 1, 1)])
    migration = importlib.import_module(
        "server.alembic.versions.20260811_0002_seed_sme_extraction_prompt"
    )
    assert migration.revision == HEAD and migration.down_revision == BASE
    _run(migration, engine, migration.upgrade)
    _run(migration, engine, migration.upgrade)
    with engine.connect() as conn:
        seeded = conn.execute(
            text("SELECT version_number FROM prompt_versions WHERE version_id=:id"),
            {"id": SEEDED_ID},
        ).scalar_one()
        assert seeded == expected
        assert len(_active(conn)) == 1
        assert _active(conn, "gad") == [{"version_id": "gad-v1", "version_number": 1}]
    engine.dispose()


def test_downgrade_restores_highest_when_no_later_active_version(tmp_path):
    engine = _engine(tmp_path, [("sme-v1", "sme", 1, 0), ("sme-v2", "sme", 2, 1)])
    migration = importlib.import_module(
        "server.alembic.versions.20260811_0002_seed_sme_extraction_prompt"
    )
    _run(migration, engine, migration.upgrade)
    _run(migration, engine, migration.downgrade)
    with engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT 1 FROM prompt_versions WHERE version_id=:id"),
                {"id": SEEDED_ID},
            ).scalar()
            is None
        )
        assert _active(conn) == [{"version_id": "sme-v2", "version_number": 2}]
    engine.dispose()


def test_downgrade_preserves_later_administrator_active_version(tmp_path):
    engine = _engine(tmp_path, [("sme-v1", "sme", 1, 0), ("sme-v2", "sme", 2, 1)])
    migration = importlib.import_module(
        "server.alembic.versions.20260811_0002_seed_sme_extraction_prompt"
    )
    _run(migration, engine, migration.upgrade)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE prompt_versions SET is_active=0 WHERE agent_id='sme'")
        )
        conn.execute(
            text(
                "INSERT INTO prompt_versions VALUES ("
                "'admin-v4', 'sme', 4, 'admin', 1, 'admin', '2026-01-02', NULL)"
            )
        )
    _run(migration, engine, migration.downgrade)
    with engine.connect() as conn:
        assert _active(conn) == [{"version_id": "admin-v4", "version_number": 4}]
    engine.dispose()
