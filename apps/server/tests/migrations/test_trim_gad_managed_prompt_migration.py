"""Verify the GAD managed-prompt trim migration."""

from __future__ import annotations

import importlib
import uuid

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, text

BASE, HEAD = "20260829_0002", "20260829_0003"
SEEDED_ID = "c3d4e5f6-a7b8-9012-cdef-345678901234"
MODULE = "server.alembic.versions.20260829_0003_trim_gad_managed_prompt"


def _run(engine, operation):
    with engine.begin() as conn:
        context = MigrationContext.configure(conn)
        with Operations.context(context):
            operation()


def _engine(tmp_path, rows):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'gadprompt.db'}")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE prompt_versions ("
                "version_id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, "
                "version_number INTEGER NOT NULL, prompt_text TEXT NOT NULL, "
                "is_active BOOLEAN NOT NULL, motivation TEXT, "
                "created_at DATETIME NOT NULL, updated_by TEXT NULL, "
                "CONSTRAINT uq_prompt_versions_agent_version "
                "UNIQUE (agent_id, version_number))"
            )
        )
        conn.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)")
        )
        conn.execute(text("INSERT INTO alembic_version VALUES (:r)"), {"r": BASE})
        for vid, agent, number, active, ptext in rows:
            conn.execute(
                text(
                    "INSERT INTO prompt_versions VALUES "
                    "(:id, :agent, :n, :pt, :a, 'seed', '2026-01-01', NULL)"
                ),
                {"id": vid, "agent": agent, "n": number, "pt": ptext, "a": active},
            )
    return engine


def _active(conn, agent="gad"):
    return (
        conn.execute(
            text(
                "SELECT version_id, prompt_text FROM prompt_versions "
                "WHERE agent_id=:a AND is_active=1 ORDER BY version_number"
            ),
            {"a": agent},
        )
        .mappings()
        .all()
    )


def test_upgrade_seeds_trimmed_prompt_and_is_idempotent(tmp_path):
    old = (
        "You are a GAD fact extractor.\n\nCRITERIA:\n"
        "GAD-01 ... Count each unique instance ..."
    )
    engine = _engine(
        tmp_path, [("gad-v1", "gad", 1, 1, old), ("sme-v1", "sme", 1, 1, "x")]
    )
    migration = importlib.import_module(MODULE)
    assert migration.revision == HEAD and migration.down_revision == BASE
    _run(engine, migration.upgrade)
    _run(engine, migration.upgrade)  # idempotent
    with engine.connect() as conn:
        active = _active(conn)
        assert len(active) == 1
        assert uuid.UUID(active[0]["version_id"]) == uuid.UUID(SEEDED_ID)
        text_ = active[0]["prompt_text"]
        assert "OUTPUT FORMAT:" in text_
        assert "CRITERIA:" not in text_
        assert "Count each unique instance" not in text_
        assert "Do NOT count" not in text_
        # SME prompt untouched
        assert _active(conn, "sme")[0]["version_id"] == "sme-v1"
    engine.dispose()


def test_downgrade_restores_previous_active(tmp_path):
    old = "OLD GAD PROMPT WITH CRITERIA SECTION"
    engine = _engine(tmp_path, [("gad-v1", "gad", 1, 1, old)])
    migration = importlib.import_module(MODULE)
    _run(engine, migration.upgrade)
    _run(engine, migration.downgrade)
    with engine.connect() as conn:
        active = _active(conn)
        assert len(active) == 1
        assert active[0]["version_id"] == "gad-v1"
        assert (
            conn.execute(
                text("SELECT 1 FROM prompt_versions WHERE version_id=:id"),
                {"id": SEEDED_ID},
            ).scalar()
            is None
        )
    engine.dispose()
