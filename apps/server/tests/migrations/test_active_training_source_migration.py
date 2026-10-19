from __future__ import annotations

import pytest
from alembic.command import upgrade
from alembic.config import Config
from server.tests.migrations.test_evaluation_rubric_provenance_migration import _run
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError


@pytest.mark.parametrize("already_present", [False, True])
def test_migration_preserves_existing_training_jobs(tmp_path, already_present):
    path = tmp_path / "sources.db"
    url = f"sqlite+pysqlite:///{path}"
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)")
        )
        connection.execute(text("INSERT INTO alembic_version VALUES ('20261015_0001')"))
        extra = (
            ", is_active_training_source BOOLEAN NOT NULL DEFAULT 0"
            if already_present
            else ""
        )
        connection.execute(
            text(
                "CREATE TABLE dpo_training_jobs (job_id TEXT PRIMARY KEY, "
                f"agent_id TEXT, pairs_content TEXT{extra})"
            )
        )
        connection.execute(
            text(
                "INSERT INTO dpo_training_jobs (job_id,agent_id,pairs_content) "
                "VALUES ('old','gad','preserved')"
            )
        )
        if already_present:
            connection.execute(
                text("UPDATE dpo_training_jobs SET is_active_training_source=1")
            )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX uq_dpo_training_jobs_active_source "
                    "ON dpo_training_jobs (agent_id) "
                    "WHERE is_active_training_source=1"
                )
            )
    config = Config("apps/server/alembic.ini")
    config.set_main_option("script_location", "apps/server/alembic")
    config.set_main_option("sqlalchemy.url", url)
    _run(upgrade, config, "20261019_0001")
    with engine.connect() as connection:
        row = (
            connection.execute(text("SELECT * FROM dpo_training_jobs")).mappings().one()
        )
        assert row["pairs_content"] == "preserved"
        assert bool(row["is_active_training_source"]) is already_present
        indexes = inspect(connection).get_indexes("dpo_training_jobs")
        assert any(
            i["name"] == "uq_dpo_training_jobs_active_source" and i["unique"]
            for i in indexes
        )
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE dpo_training_jobs SET is_active_training_source=1")
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO dpo_training_jobs "
                    "(job_id,agent_id,pairs_content,is_active_training_source) "
                    "VALUES ('duplicate','gad','other',1)"
                )
            )
    engine.dispose()
