"""Tests for Alembic migration 20260829_0005_criterion_agnostic_agent_prompts."""

from __future__ import annotations

import importlib
import uuid
from typing import Any

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, text

BASE_REVISION = "20260829_0004"
TARGET_REVISION = "20260829_0005"
MIG_MODULE = "server.alembic.versions.20260829_0005_criterion_agnostic_agent_prompts"


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


def _create_sqlite_db(tmp_path, rows: list[tuple[Any, ...]]):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'prompts_test.db'}")
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


def _get_active_prompts(engine, agent_id: str):
    with engine.connect() as conn:
        return (
            conn.execute(
                text(
                    "SELECT version_id, version_number, prompt_text "
                    "FROM prompt_versions WHERE agent_id = :agent AND is_active = 1 "
                    "ORDER BY version_number ASC"
                ),
                {"agent": agent_id},
            )
            .mappings()
            .all()
        )


def test_migration_metadata():
    mig = _get_mig()
    assert mig.revision == TARGET_REVISION
    assert mig.down_revision == BASE_REVISION


def test_migration_replaces_legacy_defaults_for_both_agents(tmp_path):
    mig = _get_mig()
    legacy_gad = "You are a GAD fact extractor.\n\nGAD-01: count items.\nGAD-02: ratio."
    legacy_itso = (
        "You are an ITSO evaluator.\n\n- ITSO-01: No IP Issue\n- ITSO-02: References"
    )

    engine = _create_sqlite_db(
        tmp_path,
        [
            ("gad-v1", "gad", 1, True, legacy_gad),
            ("itso-v1", "itso", 1, True, legacy_itso),
            ("sme-v1", "sme", 1, True, "SME Prompt"),
        ],
    )

    _run_upgrade(engine)

    active_gad = _get_active_prompts(engine, "gad")
    assert len(active_gad) == 1
    assert uuid.UUID(active_gad[0]["version_id"]) == mig.GAD_PROMPT_VERSION_ID
    assert active_gad[0]["version_number"] == 2
    assert active_gad[0]["prompt_text"] == mig.CRITERION_AGNOSTIC_GAD_PROMPT

    active_itso = _get_active_prompts(engine, "itso")
    assert len(active_itso) == 1
    assert uuid.UUID(active_itso[0]["version_id"]) == mig.ITSO_PROMPT_VERSION_ID
    assert active_itso[0]["version_number"] == 2
    assert active_itso[0]["prompt_text"] == mig.CRITERION_AGNOSTIC_ITSO_PROMPT

    # SME remains untouched
    active_sme = _get_active_prompts(engine, "sme")
    assert len(active_sme) == 1
    assert active_sme[0]["version_id"] == "sme-v1"

    engine.dispose()


def test_migration_preserves_generic_active_admin_prompt(tmp_path):
    mig = _get_mig()
    generic_admin_gad = "Custom generic GAD role prompt with no hardcoded criteria."
    legacy_itso = "You are an ITSO evaluator.\n\n- ITSO-01: No IP Issue"

    admin_gad_vid = str(uuid.uuid4())
    engine = _create_sqlite_db(
        tmp_path,
        [
            (admin_gad_vid, "gad", 1, True, generic_admin_gad),
            ("itso-v1", "itso", 1, True, legacy_itso),
        ],
    )

    _run_upgrade(engine)

    # GAD should remain on the admin's generic version (not superseded)
    active_gad = _get_active_prompts(engine, "gad")
    assert len(active_gad) == 1
    assert active_gad[0]["version_id"] == admin_gad_vid
    assert active_gad[0]["prompt_text"] == generic_admin_gad

    with engine.connect() as conn:
        mig_gad_row = conn.execute(
            text("SELECT 1 FROM prompt_versions WHERE version_id = :id"),
            {"id": str(mig.GAD_PROMPT_VERSION_ID)},
        ).scalar()
        assert mig_gad_row is None

    # ITSO had legacy fixed codes, so it gets upgraded
    active_itso = _get_active_prompts(engine, "itso")
    assert len(active_itso) == 1
    assert uuid.UUID(active_itso[0]["version_id"]) == mig.ITSO_PROMPT_VERSION_ID

    engine.dispose()


def test_migration_does_not_misclassify_generic_hyphenated_agent_wording(tmp_path):
    generic_prompt = "Use GAD-specific guidance supplied by the runtime snapshot."
    prompt_id = str(uuid.uuid4())
    engine = _create_sqlite_db(
        tmp_path,
        [(prompt_id, "gad", 1, True, generic_prompt)],
    )

    _run_upgrade(engine)

    active_gad = _get_active_prompts(engine, "gad")
    assert len(active_gad) == 1
    assert active_gad[0]["version_id"] == prompt_id
    assert active_gad[0]["prompt_text"] == generic_prompt
    engine.dispose()


def test_migration_idempotent_rerun(tmp_path):
    mig = _get_mig()
    legacy_gad = "You are a GAD fact extractor.\n\nGAD-01: count items."
    legacy_itso = "You are an ITSO evaluator.\n\n- ITSO-01: No IP Issue"

    engine = _create_sqlite_db(
        tmp_path,
        [
            ("gad-v1", "gad", 1, True, legacy_gad),
            ("itso-v1", "itso", 1, True, legacy_itso),
        ],
    )

    _run_upgrade(engine)
    _run_upgrade(engine)  # Rerun must succeed cleanly

    active_gad = _get_active_prompts(engine, "gad")
    assert len(active_gad) == 1
    assert uuid.UUID(active_gad[0]["version_id"]) == mig.GAD_PROMPT_VERSION_ID

    active_itso = _get_active_prompts(engine, "itso")
    assert len(active_itso) == 1
    assert uuid.UUID(active_itso[0]["version_id"]) == mig.ITSO_PROMPT_VERSION_ID

    engine.dispose()


def test_migration_idempotent_reactivation_when_active_is_legacy(tmp_path):
    mig = _get_mig()
    legacy_gad_1 = "GAD-01 legacy prompt v1"
    legacy_gad_3 = "GAD-01 legacy prompt v3"

    engine = _create_sqlite_db(
        tmp_path,
        [
            ("gad-v1", "gad", 1, False, legacy_gad_1),
            (
                str(mig.GAD_PROMPT_VERSION_ID),
                "gad",
                2,
                False,
                mig.CRITERION_AGNOSTIC_GAD_PROMPT,
            ),
            ("gad-v3", "gad", 3, True, legacy_gad_3),
        ],
    )

    _run_upgrade(engine)

    active_gad = _get_active_prompts(engine, "gad")
    assert len(active_gad) == 1
    assert uuid.UUID(active_gad[0]["version_id"]) == mig.GAD_PROMPT_VERSION_ID
    assert active_gad[0]["version_number"] == 2

    engine.dispose()


def test_migration_existing_row_content_mismatch_raises(tmp_path):
    mig = _get_mig()
    corrupted_mig_prompt = "Corrupted or altered prompt text for GAD migration row"

    engine = _create_sqlite_db(
        tmp_path,
        [
            (str(mig.GAD_PROMPT_VERSION_ID), "gad", 1, True, corrupted_mig_prompt),
        ],
    )

    with pytest.raises(
        RuntimeError, match="does not match expected migration definition"
    ):
        _run_upgrade(engine)

    engine.dispose()


def test_downgrade_unconditionally_raises_runtime_error():
    mig = _get_mig()
    with pytest.raises(
        RuntimeError,
        match="Downgrade is not supported for criterion-agnostic",
    ):
        mig.downgrade()


def test_postgres_uuid_binding_adapter():
    mig = _get_mig()
    test_uuid = uuid.uuid4()

    pg_type, pg_val = mig._bind_uuid(True, test_uuid)
    assert isinstance(pg_type, sa.Uuid)
    assert pg_type.as_uuid is True
    assert isinstance(pg_val, uuid.UUID)
    assert pg_val == test_uuid

    pg_type2, pg_val2 = mig._bind_uuid(True, str(test_uuid))
    assert isinstance(pg_type2, sa.Uuid)
    assert isinstance(pg_val2, uuid.UUID)
    assert pg_val2 == test_uuid

    sqlite_type, sqlite_val = mig._bind_uuid(False, test_uuid)
    assert isinstance(sqlite_type, sa.String)
    assert isinstance(sqlite_val, str)
    assert sqlite_val == str(test_uuid)
