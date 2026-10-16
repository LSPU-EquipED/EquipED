"""Offline SQLite coverage for the reconstructed 20261015 schema revision."""

from __future__ import annotations

import os
from pathlib import Path

from alembic.command import downgrade, upgrade
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

ROOT = Path(__file__).resolve().parents[2]
REV = "20261015_0001"
DOWN = "20261011_0001"


def _config(url: str) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    return config


def _run(command, config: Config, revision: str) -> None:
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


def _stamp_predecessor(engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)")
        )
        conn.execute(
            text("INSERT INTO alembic_version VALUES (:revision)"),
            {"revision": DOWN},
        )


def test_upgrade_reconstructs_schema_and_downgrade_removes_it(tmp_path):
    url = f"sqlite+pysqlite:///{tmp_path / 'program_outcomes_citation_cache.db'}"
    engine = create_engine(url)
    _stamp_predecessor(engine)

    _run(upgrade, _config(url), REV)

    with engine.connect() as conn:
        assert MigrationContext.configure(conn).get_current_revision() == REV
        inspector = inspect(conn)
        assert {"program_outcomes", "citation_cache"} <= set(
            inspector.get_table_names()
        )

        program_columns = {
            column["name"]: column
            for column in inspector.get_columns("program_outcomes")
        }
        assert set(program_columns) == {
            "program_outcome_id",
            "program_code",
            "program_name",
            "outcome_id",
            "program_outcome",
            "performance_indicator",
            "created_at",
        }
        assert program_columns["program_outcome_id"]["primary_key"] == 1
        assert program_columns["program_code"]["nullable"] is True
        assert program_columns["program_name"]["type"].length == 200
        assert program_columns["outcome_id"]["type"].length == 20
        assert program_columns["created_at"]["nullable"] is False
        assert program_columns["created_at"]["default"] is not None
        assert {
            index["name"] for index in inspector.get_indexes("program_outcomes")
        } == {"ix_program_outcomes_program_code"}

        citation_columns = {
            column["name"]: column for column in inspector.get_columns("citation_cache")
        }
        assert set(citation_columns) == {
            "id",
            "doi_hash",
            "outcome",
            "cached_at",
            "expires_at",
            "retain_until",
        }
        assert citation_columns["id"]["primary_key"] == 1
        assert citation_columns["doi_hash"]["type"].length == 64
        assert citation_columns["outcome"]["type"].length == 20
        assert citation_columns["cached_at"]["default"] is not None
        assert citation_columns["expires_at"]["default"] is None
        assert citation_columns["retain_until"]["default"] is None

        citation_indexes = {
            index["name"]: index for index in inspector.get_indexes("citation_cache")
        }
        assert set(citation_indexes) >= {
            "ix_citation_cache_doi_hash",
            "ix_citation_cache_expires_at",
            "ix_citation_cache_retain_until",
        }
        sqlite_unique_indexes = conn.exec_driver_sql(
            "PRAGMA index_list('citation_cache')"
        ).all()
        assert any(index[2] for index in sqlite_unique_indexes)
        assert (
            conn.execute(text("SELECT COUNT(*) FROM program_outcomes")).scalar_one()
            == 0
        )
        assert (
            conn.execute(text("SELECT COUNT(*) FROM citation_cache")).scalar_one() == 0
        )

    _run(downgrade, _config(url), DOWN)
    with engine.connect() as conn:
        assert MigrationContext.configure(conn).get_current_revision() == DOWN
        assert not {"program_outcomes", "citation_cache"} & set(
            inspect(conn).get_table_names()
        )
    engine.dispose()
