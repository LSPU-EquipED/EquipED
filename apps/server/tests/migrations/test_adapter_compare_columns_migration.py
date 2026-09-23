"""Tests for 20260923_0001_add_adapter_compare_columns migration."""

from __future__ import annotations

import os
import uuid
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


def _setup_test_database(engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)")
        )
        conn.execute(text("INSERT INTO alembic_version VALUES ('20260918_0003')"))

        conn.execute(
            text("CREATE TABLE evaluation_jobs (evaluation_id CHAR(36) PRIMARY KEY)")
        )
        conn.execute(
            text(
                "CREATE TABLE model_validations ("
                "validation_id CHAR(36) PRIMARY KEY, "
                "evaluation_id CHAR(36) NOT NULL, "
                "created_by CHAR(36) NOT NULL, "
                "created_at DATETIME NOT NULL"
                ")"
            )
        )


def test_upgrade_adds_columns_and_downgrade_drops_them(tmp_path):
    """Upgrade adds lora_scale/model_variant/compare_group_id, all nullable and
    able to hold real values; downgrade removes all three plus the index."""
    db_path = tmp_path / "test_migration_adapter_compare_columns.db"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)

    _setup_test_database(engine)

    # Run upgrade
    _run_migration(alembic_upgrade, db_url, "20260923_0001")

    inspector = inspect(engine)
    job_columns = {c["name"] for c in inspector.get_columns("evaluation_jobs")}
    assert "lora_scale" in job_columns

    validation_columns = {c["name"] for c in inspector.get_columns("model_validations")}
    assert "model_variant" in validation_columns
    assert "compare_group_id" in validation_columns

    indexes = {i["name"] for i in inspector.get_indexes("model_validations")}
    assert "idx_model_validations_compare_group_id" in indexes

    job_id = str(uuid.uuid4())
    job_id_with_scale = str(uuid.uuid4())
    validation_id_null = str(uuid.uuid4())
    validation_id_filled = str(uuid.uuid4())
    evaluation_id = str(uuid.uuid4())
    created_by = str(uuid.uuid4())
    compare_group_id = str(uuid.uuid4())

    with engine.begin() as conn:
        # NULL lora_scale (existing-row default)
        conn.execute(
            text(
                "INSERT INTO evaluation_jobs (evaluation_id, lora_scale) "
                "VALUES (:eid, NULL)"
            ),
            {"eid": job_id},
        )
        # Non-null lora_scale (explicit override)
        conn.execute(
            text(
                "INSERT INTO evaluation_jobs (evaluation_id, lora_scale) "
                "VALUES (:eid, :scale)"
            ),
            {"eid": job_id_with_scale, "scale": 0.5},
        )
        # NULL model_variant / compare_group_id (a normal, non-compare validation)
        conn.execute(
            text(
                "INSERT INTO model_validations "
                "(validation_id, evaluation_id, created_by, created_at, "
                "model_variant, compare_group_id) "
                "VALUES (:vid, :eid, :cby, '2026-09-23 00:00:00', NULL, NULL)"
            ),
            {"vid": validation_id_null, "eid": evaluation_id, "cby": created_by},
        )
        # Real model_variant / compare_group_id values (a compare-pair validation)
        conn.execute(
            text(
                "INSERT INTO model_validations "
                "(validation_id, evaluation_id, created_by, created_at, "
                "model_variant, compare_group_id) "
                "VALUES (:vid, :eid, :cby, '2026-09-23 00:00:00', "
                ":variant, :group_id)"
            ),
            {
                "vid": validation_id_filled,
                "eid": evaluation_id,
                "cby": created_by,
                "variant": "adapter",
                "group_id": compare_group_id,
            },
        )

    with engine.connect() as conn:
        job_rows = (
            conn.execute(
                text(
                    "SELECT evaluation_id, lora_scale FROM evaluation_jobs "
                    "ORDER BY evaluation_id"
                )
            )
            .mappings()
            .all()
        )
        by_id = {row["evaluation_id"]: row["lora_scale"] for row in job_rows}
        assert by_id[job_id] is None
        assert by_id[job_id_with_scale] == 0.5

        validation_rows = (
            conn.execute(
                text(
                    "SELECT validation_id, model_variant, compare_group_id "
                    "FROM model_validations ORDER BY validation_id"
                )
            )
            .mappings()
            .all()
        )
        by_vid = {row["validation_id"]: row for row in validation_rows}
        assert by_vid[validation_id_null]["model_variant"] is None
        assert by_vid[validation_id_null]["compare_group_id"] is None
        assert by_vid[validation_id_filled]["model_variant"] == "adapter"
        assert by_vid[validation_id_filled]["compare_group_id"] == compare_group_id

    # Run downgrade
    _run_migration(alembic_downgrade, db_url, "20260918_0003")

    inspector = inspect(engine)
    job_columns = {c["name"] for c in inspector.get_columns("evaluation_jobs")}
    assert "lora_scale" not in job_columns

    validation_columns = {c["name"] for c in inspector.get_columns("model_validations")}
    assert "model_variant" not in validation_columns
    assert "compare_group_id" not in validation_columns

    indexes = {i["name"] for i in inspector.get_indexes("model_validations")}
    assert "idx_model_validations_compare_group_id" not in indexes
