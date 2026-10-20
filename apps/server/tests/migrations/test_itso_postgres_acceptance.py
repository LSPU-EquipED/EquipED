"""Guarded opt-in ITSO PostgreSQL DDL acceptance in a disposable local schema."""

# Long DDL fixture strings are kept literal to mirror the isolated catalog.
# ruff: noqa: E501

from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from alembic import command
from server.tests.migrations.test_evaluation_rubric_provenance_migration import _run
from server.tests.migrations.test_itso_source_assessment_migrations import config
from sqlalchemy import MetaData, Table, create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

RUN = "RUN_ITSO_POSTGRES_TESTS"


_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
_ROUTING_QUERY_KEYS = {
    "host",
    "hostaddr",
    "port",
    "dbname",
    "service",
    "servicefile",
    "passfile",
    "user",
    "password",
}


def _identity(url: str, *, require_local: bool = True):
    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql":
        raise ValueError("PostgreSQL acceptance requires a PostgreSQL URL")
    if require_local and _ROUTING_QUERY_KEYS.intersection(parsed.query):
        raise ValueError("PostgreSQL acceptance URL contains query routing overrides")
    host = (parsed.host or "").lower()
    if require_local and host not in _LOOPBACK_HOSTS:
        raise ValueError("PostgreSQL acceptance requires a local host")
    host = "loopback" if host in _LOOPBACK_HOSTS else host
    return (host, parsed.port or 5432, parsed.database)


def _alembic_config(url):
    rendered_url = url.render_as_string(hide_password=False)
    # ConfigParser treats percent signs as interpolation markers. Escape them
    # when storing the URL; get_main_option() then returns the original URL.
    cfg = config(rendered_url.replace("%", "%%"))
    return cfg


def _guarded_url():
    if os.getenv(RUN) != "YES":
        pytest.skip(f"set {RUN}=YES to opt in")
    if os.getenv("POSTGRES_TEST_DISPOSABLE") != "YES":
        pytest.fail("POSTGRES_TEST_DISPOSABLE=YES is required when opted in")
    raw = os.getenv("POSTGRES_TEST_DATABASE_URL")
    if not raw:
        pytest.fail("POSTGRES_TEST_DATABASE_URL is required")
    try:
        identity = _identity(raw)
        live = os.getenv("DATABASE_URL")
        if live and identity == _identity(live, require_local=False):
            pytest.fail("refusing DATABASE_URL identity for acceptance test")
    except ValueError as exc:
        pytest.fail(str(exc))
    return make_url(raw)


def test_url_guard_rejects_remote_hosts_without_connecting():
    for url in ("postgresql://example.invalid/db", "postgresql://10.0.0.2/db"):
        with pytest.raises(ValueError, match="local host"):
            _identity(url)


def test_url_guard_accepts_loopbacks_and_matches_database_not_login():
    identities = [
        _identity(f"postgresql+psycopg://{user}:pw@{host}/testdb")
        for host, user in (
            ("localhost", "one"),
            ("127.0.0.1", "two"),
            ("[::1]", "three"),
        )
    ]
    assert identities[0] == identities[1] == identities[2]


def test_url_guard_rejects_driver_backend_and_query_routing():
    for url in (
        "mysql+pymysql://u:p@localhost/testdb",
        "postgresql://u:p@localhost/testdb?host=remote.invalid",
        "postgresql://u:p@localhost/testdb?hostaddr=10.0.0.2",
        "postgresql://u:p@localhost/testdb?service=live",
        "postgresql://u:p@localhost/testdb?dbname=other",
    ):
        with pytest.raises(ValueError):
            _identity(url)


def test_opted_in_without_disposable_acknowledgement_fails(monkeypatch):
    monkeypatch.setenv(RUN, "YES")
    monkeypatch.delenv("POSTGRES_TEST_DISPOSABLE", raising=False)
    with pytest.raises(pytest.fail.Exception, match="POSTGRES_TEST_DISPOSABLE"):
        _guarded_url()


def test_config_preserves_password_without_emitting_it(capsys):
    secret = "synthetic-secret"
    url = make_url(f"postgresql+psycopg://test:{secret}@localhost/testdb")
    cfg = _alembic_config(url)
    assert secret in cfg.get_main_option("sqlalchemy.url")
    assert capsys.readouterr().out == ""
    assert capsys.readouterr().err == ""


def test_config_round_trips_percent_encoded_options_and_password(capsys):
    url = make_url(
        "postgresql+psycopg://test:synthetic%25password@localhost/testdb"
        "?options=-csearch_path%3Dsynthetic%20schema%25name"
    )
    cfg = _alembic_config(url)
    rendered = url.render_as_string(hide_password=False)
    assert "synthetic%25password" in rendered
    assert "options=" in rendered and "%25" in rendered and "%3D" in rendered
    assert cfg.get_main_option("sqlalchemy.url") == rendered
    assert capsys.readouterr().out == ""
    assert capsys.readouterr().err == ""


@pytest.mark.skipif(os.getenv(RUN) != "YES", reason=f"set {RUN}=YES")
def test_three_revision_postgres_upgrade_constraints_and_downgrades():
    base = _guarded_url()
    schema = "itso_accept_" + uuid4().hex[:20]
    admin = create_engine(base, pool_pre_ping=True)
    created = False
    # A unique schema is the destructive boundary; this never drops a database.
    try:
        with admin.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            created = True
        schema_url = base.set(
            query={**base.query, "options": f"-csearch_path={schema}"}
        )
        engine = create_engine(schema_url)
        try:
            with engine.begin() as db:
                db.execute(
                    text(
                        "CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)"
                    )
                )
                db.execute(text("INSERT INTO alembic_version VALUES ('20261019_0001')"))
                db.execute(text("CREATE TABLE users (user_id UUID PRIMARY KEY)"))
                db.execute(
                    text("CREATE TABLE documents (document_id UUID PRIMARY KEY)")
                )
                db.execute(
                    text(
                        "CREATE TABLE evaluation_jobs (evaluation_id UUID PRIMARY KEY)"
                    )
                )
                db.execute(
                    text(
                        "CREATE TABLE evaluation_form_snapshots (snapshot_id UUID PRIMARY KEY, evaluation_id UUID REFERENCES evaluation_jobs(evaluation_id), agent_id TEXT NOT NULL, adapter_version INTEGER NOT NULL)"
                    )
                )
                db.execute(
                    text(
                        "CREATE TABLE agent_results (result_id TEXT PRIMARY KEY, subtotal FLOAT NOT NULL)"
                    )
                )
                db.execute(text("INSERT INTO agent_results VALUES ('synthetic', 3.25)"))
            cfg = _alembic_config(schema_url)
            _run(command.upgrade, cfg, "head")
            meta = MetaData()
            assessment = Table("itso_assessments", meta, autoload_with=engine)
            fks = inspect(engine).get_foreign_keys("itso_assessments")
            assert any(fk["referred_table"] == "evaluation_jobs" for fk in fks)
            legacy_subtotal = {
                col["name"]: col for col in inspect(engine).get_columns("agent_results")
            }["subtotal"]
            assert legacy_subtotal["nullable"] is False
            _run(command.downgrade, cfg, "20261019_0001")
            assert "itso_assessments" not in inspect(engine).get_table_names()
            _run(command.upgrade, cfg, "head")
            assessment = Table("itso_assessments", MetaData(), autoload_with=engine)
            owner, doc, evaluation, form, source = [str(uuid4()) for _ in range(5)]
            assessment_id = str(uuid4())
            with engine.begin() as db:
                db.execute(text("INSERT INTO users VALUES (:id)"), {"id": owner})
                db.execute(text("INSERT INTO documents VALUES (:id)"), {"id": doc})
                db.execute(
                    text("INSERT INTO evaluation_jobs VALUES (:id)"), {"id": evaluation}
                )
                db.execute(
                    text(
                        "INSERT INTO evaluation_form_snapshots VALUES (:f,:e,'itso',2)"
                    ),
                    {"f": form, "e": evaluation},
                )
                db.execute(
                    text(
                        "INSERT INTO document_source_snapshots (snapshot_id, document_id, owner_id, source_hash, canonical_hash, extractor_version, canonicalization_version, canonical_text, page_map, reference_inventory, inventory_hash, inventory_version, inventory_complete, inventory_uncertainties) VALUES (:s,:d,:o,:h,:c,'synthetic','synthetic','synthetic','[]','[]',:i,'synthetic',false,'[]')"
                    ),
                    {
                        "s": source,
                        "d": doc,
                        "o": owner,
                        "h": "a" * 64,
                        "c": "b" * 64,
                        "i": "c" * 64,
                    },
                )
                db.execute(
                    assessment.insert().values(
                        assessment_id=assessment_id,
                        evaluation_id=evaluation,
                        document_id=doc,
                        owner_id=owner,
                        source_snapshot_id=source,
                        source_hash="a" * 64,
                        form_snapshot_id=form,
                        effective_policy_hash="d" * 64,
                        contract_version="synthetic",
                        manifest_version=2,
                        execution_status="COMPLETED",
                        scoring_complete=True,
                        subtotal=2.75,
                    )
                )
                assert (
                    db.scalar(
                        text(
                            "SELECT subtotal FROM itso_assessments WHERE assessment_id=:id"
                        ),
                        {"id": assessment_id},
                    )
                    == 2.75
                )
                with pytest.raises(IntegrityError):
                    with db.begin_nested():
                        db.execute(
                            text(
                                "INSERT INTO itso_assessments (assessment_id,evaluation_id,document_id,owner_id,source_snapshot_id,source_hash,form_snapshot_id,effective_policy_hash,contract_version,manifest_version,execution_status,scoring_complete,subtotal) VALUES (:assessment,:evaluation,:document,:owner,:source,:hash,:form,:policy,'synthetic',2,'COMPLETED',true,2.5)"
                            ),
                            {
                                "assessment": str(uuid4()),
                                "evaluation": str(uuid4()),
                                "document": doc,
                                "owner": owner,
                                "source": source,
                                "hash": "a" * 64,
                                "form": form,
                                "policy": "d" * 64,
                            },
                        )
            # Migration's existing refusal helper must retain populated history.
            policy = Table("itso_policy_versions", MetaData(), autoload_with=engine)
            owner, doc, snapshot, version, lineage = [str(uuid4()) for _ in range(5)]
            with engine.begin() as db:
                db.execute(text("INSERT INTO users VALUES (:id)"), {"id": owner})
                db.execute(text("INSERT INTO documents VALUES (:id)"), {"id": doc})
                db.execute(
                    text(
                        "INSERT INTO document_source_snapshots (snapshot_id, document_id, owner_id, source_hash, canonical_hash, extractor_version, canonicalization_version, canonical_text, page_map, reference_inventory, inventory_hash, inventory_version, inventory_complete, inventory_uncertainties) VALUES (:s,:d,:o,:h,:c,'synthetic','synthetic','synthetic','[]','[]',:i,'synthetic',false,'[]')"
                    ),
                    {
                        "s": snapshot,
                        "d": doc,
                        "o": owner,
                        "h": "e" * 64,
                        "c": "f" * 64,
                        "i": "1" * 64,
                    },
                )
                db.execute(
                    policy.insert().values(
                        policy_version_id=version,
                        lineage_id=lineage,
                        version=1,
                        kind="egress",
                        scope="global",
                        criterion_id="",
                        source_snapshot_id=snapshot,
                        source_hash="f" * 64,
                        payload={"kind": "egress"},
                        payload_hash="2" * 64,
                        created_by=owner,
                        created_at=datetime.now(UTC),
                    )
                )
            with pytest.raises(RuntimeError, match="refuses to delete"):
                _run(command.downgrade, cfg, "20261020_0002")
            with engine.connect() as db:
                assert db.scalar(text("SELECT COUNT(*) FROM itso_policy_versions")) == 1
            engine.dispose()
        finally:
            engine.dispose()
    finally:
        if created:
            with admin.begin() as conn:
                conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
