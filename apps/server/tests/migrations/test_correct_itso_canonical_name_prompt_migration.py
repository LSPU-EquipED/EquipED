"""Tests for Alembic migration 20260918_0001_correct_itso_canonical_name_prompt."""

from __future__ import annotations

import importlib
import uuid

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, text

BASE_REVISION = "20260917_0001"
TARGET_REVISION = "20260918_0001"
MIG_MODULE = "server.alembic.versions.20260918_0001_correct_itso_canonical_name_prompt"


def _get_mig():
    return importlib.import_module(MIG_MODULE)


def _run_upgrade(engine):
    mig = _get_mig()
    with engine.begin() as conn:
        context = MigrationContext.configure(conn)
        with Operations.context(context):
            mig.upgrade()


def _run_downgrade(engine):
    mig = _get_mig()
    with engine.begin() as conn:
        context = MigrationContext.configure(conn)
        with Operations.context(context):
            mig.downgrade()


def _create_sqlite_db(tmp_path, rows: list[tuple]):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'itso_prompt_test.db'}")
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
        conn.execute(
            text("INSERT INTO alembic_version VALUES (:r)"), {"r": BASE_REVISION}
        )
        for vid, agent, number, active, ptext in rows:
            conn.execute(
                text(
                    "INSERT INTO prompt_versions VALUES "
                    "(:id, :agent, :n, :pt, :a, 'seed', '2026-01-01 00:00:00', NULL)"
                ),
                {"id": str(vid), "agent": agent, "n": number, "pt": ptext, "a": active},
            )
    return engine


def test_migration_metadata():
    mig = _get_mig()
    assert mig.revision == TARGET_REVISION
    assert mig.down_revision == BASE_REVISION


def test_upgrade_corrects_active_itso_prompt_directive(tmp_path):
    itso_vid = str(uuid.uuid4())
    legacy_itso_text = (
        "You are an IT Security Officer (ITSO) evaluator for Student Learning "
        "Materials (SLMs). Assess five rubric criteria: IP concerns, proper "
        "references, faculty ownership, student confidentiality, and "
        "teacher/student digital rights."
    )
    other_agent_vid = str(uuid.uuid4())
    sme_text = "You are an SME evaluator for Self-Paced Learning Modules."

    engine = _create_sqlite_db(
        tmp_path,
        [
            (itso_vid, "itso", 1, True, legacy_itso_text),
            (other_agent_vid, "sme", 1, True, sme_text),
        ],
    )

    _run_upgrade(engine)

    with engine.connect() as conn:
        res = conn.execute(
            text("SELECT prompt_text FROM prompt_versions WHERE version_id = :id"),
            {"id": itso_vid},
        ).scalar_one()

        assert res.startswith(
            "You are an Innovation and Technology Support Office (ITSO) evaluator "
            "for Student Learning Materials (SLMs)."
        )
        assert "Assess five rubric criteria: IP concerns, proper references" in res

        # Ensure other agents are untouched
        sme_res = conn.execute(
            text("SELECT prompt_text FROM prompt_versions WHERE version_id = :id"),
            {"id": other_agent_vid},
        ).scalar_one()
        assert sme_res == sme_text


def test_upgrade_is_idempotent(tmp_path):
    itso_vid = str(uuid.uuid4())
    already_canonical = (
        "You are an Innovation and Technology Support Office (ITSO) evaluator "
        "for Student Learning Materials (SLMs). Remaining instructions."
    )

    engine = _create_sqlite_db(
        tmp_path,
        [
            (itso_vid, "itso", 1, True, already_canonical),
        ],
    )

    _run_upgrade(engine)

    with engine.connect() as conn:
        res = conn.execute(
            text("SELECT prompt_text FROM prompt_versions WHERE version_id = :id"),
            {"id": itso_vid},
        ).scalar_one()
        assert res == already_canonical


def test_downgrade_reverts_active_itso_prompt_directive(tmp_path):
    itso_vid = str(uuid.uuid4())
    canonical_text = (
        "You are an Innovation and Technology Support Office (ITSO) evaluator "
        "for Student Learning Materials (SLMs). "
        "Assess five rubric criteria: IP concerns, proper references."
    )

    engine = _create_sqlite_db(
        tmp_path,
        [
            (itso_vid, "itso", 1, True, canonical_text),
        ],
    )

    _run_downgrade(engine)

    with engine.connect() as conn:
        res = conn.execute(
            text("SELECT prompt_text FROM prompt_versions WHERE version_id = :id"),
            {"id": itso_vid},
        ).scalar_one()
        assert res.startswith(
            "You are an IT Security Officer (ITSO) evaluator for Student Learning "
            "Materials (SLMs)."
        )
        assert "Assess five rubric criteria: IP concerns, proper references." in res
