"""New revision only: synthetic SQLite catalog, never the application database."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from alembic import command
from server.tests.migrations.test_evaluation_rubric_provenance_migration import _run
from server.tests.migrations.test_itso_source_assessment_migrations import config
from sqlalchemy import MetaData, Table, create_engine, inspect, text


def catalog(tmp_path):
    url = f"sqlite+pysqlite:///{tmp_path / 'workflow-ddl.db'}"
    engine = create_engine(url)
    with engine.begin() as db:
        db.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)")
        )
        db.execute(text("INSERT INTO alembic_version VALUES ('20261019_0001')"))
        db.execute(text("CREATE TABLE users (user_id CHAR(32) PRIMARY KEY)"))
        db.execute(text("CREATE TABLE documents (document_id CHAR(32) PRIMARY KEY)"))
        db.execute(
            text("CREATE TABLE evaluation_jobs (evaluation_id CHAR(32) PRIMARY KEY)")
        )
        db.execute(
            text(
                "CREATE TABLE evaluation_form_snapshots "
                "(snapshot_id CHAR(32) PRIMARY KEY, evaluation_id CHAR(32), "
                "agent_id TEXT, adapter_version INTEGER)"
            )
        )
    cfg = config(url)
    _run(command.upgrade, cfg, "20261020_0002")
    return cfg, engine


def test_empty_schema_downgrade_is_reversible_and_parent_binds_form(tmp_path):
    cfg, engine = catalog(tmp_path)
    _run(command.upgrade, cfg, "head")
    columns = {c["name"]: c for c in inspect(engine).get_columns("itso_assessments")}
    assert not columns["form_snapshot_id"]["nullable"]
    assert not columns["effective_policy_hash"]["nullable"]
    assert "itso_policy_activation_events" in inspect(engine).get_table_names()
    _run(command.downgrade, cfg, "20261020_0002")
    assert "itso_policy_versions" not in inspect(engine).get_table_names()
    assert "form_snapshot_id" not in {
        c["name"] for c in inspect(engine).get_columns("itso_assessments")
    }
    _run(command.upgrade, cfg, "head")
    engine.dispose()


def test_populated_policy_downgrade_refuses_without_erasing_history(tmp_path):
    cfg, engine = catalog(tmp_path)
    _run(command.upgrade, cfg, "head")
    meta = MetaData()
    policy = Table("itso_policy_versions", meta, autoload_with=engine)
    source = Table("document_source_snapshots", meta, autoload_with=engine)
    actor, doc, snapshot, version, lineage = [uuid4() for _ in range(5)]
    with engine.begin() as db:
        db.execute(text("INSERT INTO users VALUES (:id)"), {"id": actor.hex})
        db.execute(text("INSERT INTO documents VALUES (:id)"), {"id": doc.hex})
        db.execute(
            source.insert().values(
                snapshot_id=snapshot.hex,
                owner_id=actor.hex,
                document_id=doc.hex,
                source_hash="a" * 64,
                canonical_hash="b" * 64,
                canonical_text="synthetic",
                page_map=[],
                reference_inventory=[],
                inventory_hash="c" * 64,
                inventory_version="synthetic",
                inventory_complete=False,
                inventory_uncertainties=[],
                extractor_version="synthetic",
                canonicalization_version="synthetic",
            )
        )
        db.execute(
            policy.insert().values(
                policy_version_id=version.hex,
                lineage_id=lineage.hex,
                version=1,
                kind="egress",
                scope="global",
                criterion_id="",
                source_snapshot_id=snapshot.hex,
                source_hash="b" * 64,
                payload={"kind": "egress"},
                payload_hash="d" * 64,
                created_by=actor.hex,
                created_at=datetime.now(UTC),
            )
        )
    with pytest.raises(RuntimeError, match="refuses to delete"):
        _run(command.downgrade, cfg, "20261020_0002")
    with engine.connect() as db:
        assert db.scalar(text("SELECT COUNT(*) FROM itso_policy_versions")) == 1
        assert (
            db.scalar(text("SELECT version_num FROM alembic_version"))
            == "20261020_0003"
        )
    assert "itso_assessment_revisions" in inspect(engine).get_table_names()
    engine.dispose()
