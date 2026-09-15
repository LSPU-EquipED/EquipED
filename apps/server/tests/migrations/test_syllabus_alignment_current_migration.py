from __future__ import annotations

import importlib.util
import os
import uuid
from pathlib import Path

from alembic.command import upgrade as alembic_upgrade
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

REPO_ROOT = Path(__file__).resolve().parents[3]


def _migration_module():
    path = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "20260803_0002_make_syllabus_alignment_current.py"
    )
    spec = importlib.util.spec_from_file_location("alignment_current_migration", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_retains_only_newest_row_per_slm():
    migration = _migration_module()
    rows = [
        {"alignment_id": "new-a", "slm_document_id": "slm-a"},
        {"alignment_id": "old-a", "slm_document_id": "slm-a"},
        {"alignment_id": "new-b", "slm_document_id": "slm-b"},
        {"alignment_id": "middle-a", "slm_document_id": "slm-a"},
    ]
    assert migration._obsolete_alignment_ids(rows) == ["old-a", "middle-a"]


def test_online_migration_deduplicates_and_adds_unique_index():
    artifact_directory = REPO_ROOT / ".test-artifacts"
    artifact_directory.mkdir(exist_ok=True)
    database_path = artifact_directory / f"alignment-current-{uuid.uuid4()}.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE syllabus_alignment_runs ("
                "alignment_id CHAR(32) PRIMARY KEY, "
                "slm_document_id CHAR(32) NOT NULL, "
                "created_at DATETIME NOT NULL, "
                "status VARCHAR(20) NOT NULL)"
            )
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX uq_syllabus_alignment_active_slm "
                "ON syllabus_alignment_runs (slm_document_id) "
                "WHERE status IN ('QUEUED', 'RUNNING')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO syllabus_alignment_runs VALUES "
                "('11111111111111111111111111111111', "
                "'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', "
                "'2026-08-03 10:00:00', 'COMPLETED'),"
                "('22222222222222222222222222222222', "
                "'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', '2026-08-03 09:00:00', 'FAILED'),"
                "('33333333333333333333333333333333', "
                "'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', "
                "'2026-08-03 08:00:00', 'COMPLETED')"
            )
        )
        connection.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)")
        )
        connection.execute(text("INSERT INTO alembic_version VALUES ('20260803_0001')"))

    config = Config(str(REPO_ROOT / "server" / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    from server.core.config import get_settings

    original_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = ""
    get_settings.cache_clear()
    try:
        alembic_upgrade(config, "20260803_0002")
    finally:
        if original_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original_database_url
        get_settings.cache_clear()

    with engine.connect() as connection:
        retained = (
            connection.execute(
                text(
                    "SELECT alignment_id FROM syllabus_alignment_runs "
                    "ORDER BY alignment_id"
                )
            )
            .scalars()
            .all()
        )
    assert retained == [
        "11111111111111111111111111111111",
        "33333333333333333333333333333333",
    ]
    indexes = {
        item["name"]: item
        for item in inspect(engine).get_indexes("syllabus_alignment_runs")
    }
    assert indexes["uq_syllabus_alignment_slm"]["unique"] == 1
    engine.dispose()
    database_path.unlink(missing_ok=True)
