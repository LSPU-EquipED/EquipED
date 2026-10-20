"""Unapplied ITSO DDL against isolated SQLite; no application DB is consulted."""

from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from server.tests.migrations.test_evaluation_rubric_provenance_migration import _run
from sqlalchemy import Float, MetaData, Table, create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError


def config(url):
    cfg = Config("apps/server/alembic.ini")
    cfg.set_main_option("script_location", str(Path("apps/server/alembic").resolve()))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def test_ordered_itso_upgrade_preserves_parents_and_protects_history(tmp_path):
    url = f"sqlite+pysqlite:///{tmp_path / 'isolated-itso.db'}"
    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def enable_fks(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    # Minimal synthetic parent catalog at the verified preceding head; this is
    # not a claim that the unrelated historical migrations were all replayed.
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
                "(snapshot_id CHAR(32) PRIMARY KEY, "
                "evaluation_id CHAR(32) REFERENCES evaluation_jobs(evaluation_id), "
                "agent_id TEXT NOT NULL, adapter_version INTEGER NOT NULL)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE agent_results "
                "(result_id TEXT PRIMARY KEY, subtotal FLOAT NOT NULL)"
            )
        )
        connection.execute(text("INSERT INTO agent_results VALUES ('legacy',3.25)"))
    cfg = config(url)
    scripts = ScriptDirectory.from_config(cfg)
    assert scripts.get_heads() == ["20261020_0003"]
    assert scripts.get_revision("20261020_0003").down_revision == "20261020_0002"
    assert scripts.get_revision("20261020_0001").down_revision == "20261019_0001"
    _run(command.upgrade, cfg, "head")
    tables = {
        name: Table(name, MetaData(), autoload_with=engine)
        for name in (
            "users",
            "documents",
            "evaluation_jobs",
            "evaluation_form_snapshots",
            "document_source_snapshots",
            "itso_assessments",
        )
    }
    assert isinstance(tables["itso_assessments"].c.subtotal.type, Float)
    owner, document, evaluation, snapshot, assessment, form = [
        uuid4().hex for _ in range(6)
    ]
    with engine.begin() as connection:
        connection.execute(tables["users"].insert().values(user_id=owner))
        connection.execute(tables["documents"].insert().values(document_id=document))
        connection.execute(
            tables["evaluation_jobs"].insert().values(evaluation_id=evaluation)
        )
        connection.execute(
            tables["evaluation_form_snapshots"]
            .insert()
            .values(
                snapshot_id=form,
                evaluation_id=evaluation,
                agent_id="itso",
                adapter_version=2,
            )
        )
        connection.execute(
            tables["document_source_snapshots"]
            .insert()
            .values(
                snapshot_id=snapshot,
                document_id=document,
                owner_id=owner,
                source_hash="a" * 64,
                canonical_hash="b" * 64,
                extractor_version="test.v1",
                canonicalization_version="test.v1",
                canonical_text="Synthetic",
                page_map=[],
                reference_inventory=[],
                inventory_hash="c" * 64,
                inventory_version="test-only.regex.v1",
                inventory_complete=False,
                inventory_uncertainties=["unknown formats"],
            )
        )
        connection.execute(
            tables["itso_assessments"]
            .insert()
            .values(
                assessment_id=assessment,
                evaluation_id=evaluation,
                document_id=document,
                owner_id=owner,
                source_snapshot_id=snapshot,
                source_hash="a" * 64,
                form_snapshot_id=form,
                effective_policy_hash="d" * 64,
                contract_version="itso_evidence.v1",
                manifest_version=2,
                execution_status="COMPLETED",
                scoring_complete=True,
                subtotal=2.8,
            )
        )
        for name, key, value in (
            ("documents", "document_id", document),
            ("users", "user_id", owner),
            ("evaluation_jobs", "evaluation_id", evaluation),
            ("document_source_snapshots", "snapshot_id", snapshot),
            ("evaluation_form_snapshots", "snapshot_id", form),
        ):
            with connection.begin_nested(), pytest.raises(IntegrityError):
                connection.execute(
                    tables[name].delete().where(tables[name].c[key] == value)
                )
        assert (
            connection.scalar(
                text("SELECT subtotal FROM agent_results WHERE result_id='legacy'")
            )
            == 3.25
        )
        assert connection.scalar(text("SELECT subtotal FROM itso_assessments")) == 2.8
    assert not inspect(engine).get_columns("agent_results")[1]["nullable"]
    with pytest.raises(RuntimeError, match="refuses to delete"):
        _run(command.downgrade, cfg, "20261019_0001")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT subtotal FROM itso_assessments")) == 2.8
    engine.dispose()
