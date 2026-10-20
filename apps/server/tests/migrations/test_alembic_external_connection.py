"""Alembic migrations can participate in a caller-owned transaction."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def test_upgrade_uses_and_preserves_supplied_connection_transaction(tmp_path):
    database_path = tmp_path / "external-transaction.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)")
        )
        connection.execute(text("INSERT INTO alembic_version VALUES ('20261019_0001')"))
        connection.execute(text("CREATE TABLE users (user_id CHAR(32) PRIMARY KEY)"))
        connection.execute(
            text("CREATE TABLE documents (document_id CHAR(32) PRIMARY KEY)")
        )
        connection.execute(
            text("CREATE TABLE evaluation_jobs (evaluation_id CHAR(32) PRIMARY KEY)")
        )
        connection.execute(
            text(
                "CREATE TABLE evaluation_form_snapshots "
                "(snapshot_id CHAR(32) PRIMARY KEY, evaluation_id CHAR(32), "
                "agent_id TEXT, adapter_version INTEGER)"
            )
        )

    server_root = Path(__file__).resolve().parents[2]
    config = Config(str(server_root / "alembic.ini"))
    config.set_main_option("script_location", str(server_root / "alembic"))

    with engine.connect() as connection:
        # SQLite otherwise starts a transaction lazily and may implicitly
        # commit DDL. An explicit BEGIN makes the test exercise rollback of DDL.
        connection.exec_driver_sql("BEGIN")
        transaction = connection.get_transaction()
        config.attributes["connection"] = connection

        command.upgrade(config, "head")

        assert transaction.is_active
        assert "document_source_snapshots" in inspect(connection).get_table_names()
        assert connection.scalar(text("SELECT 1")) == 1
        transaction.rollback()

        assert connection.scalar(text("SELECT 1")) == 1
        assert "document_source_snapshots" not in inspect(connection).get_table_names()
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "20261019_0001"
        )

    engine.dispose()
