"""Tests for Alembic migration 20260829_0004_dynamic_cid_forms."""

from __future__ import annotations

import importlib
import os
import uuid
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect, make_url, text
from sqlalchemy.exc import DatabaseError, IntegrityError, InternalError

from alembic import command

_MIG_MOD = importlib.import_module(
    "server.alembic.versions.20260829_0004_dynamic_cid_forms"
)
_SME_STRATEGY_CONFIGS = _MIG_MOD._SME_STRATEGY_CONFIGS
_GAD_STRATEGY_CONFIGS = _MIG_MOD._GAD_STRATEGY_CONFIGS

REPO_ROOT = Path(__file__).resolve().parents[3]
POSTGRES_MIGRATION_FLAG = "RUN_POSTGRES_MIGRATION_TESTS"
DISPOSABLE_FLAG = "POSTGRES_TEST_DISPOSABLE"
TARGET_REVISION = "20260829_0004"
DOWN_REVISION = "20260829_0003"


def _config(url: str) -> Config:
    config = Config(str(REPO_ROOT / "server" / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


def _run(cmd, config, revision):
    from server.core.config import get_settings

    get_settings.cache_clear()
    old = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = ""
    try:
        cmd(config, revision)
    finally:
        if old is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old
        get_settings.cache_clear()


def is_same_postgres_database_identity(url_a: str, url_b: str) -> bool:
    """Return True if two PostgreSQL URLs target same host/port/db identity."""
    if not url_a or not url_b:
        return False
    u_a = make_url(url_a.strip())
    u_b = make_url(url_b.strip())
    host_a = (u_a.host or "").replace("-pooler", "").lower()
    host_b = (u_b.host or "").replace("-pooler", "").lower()
    port_a = u_a.port or 5432
    port_b = u_b.port or 5432
    db_a = (u_a.database or "").lstrip("/")
    db_b = (u_b.database or "").lstrip("/")
    return host_a == host_b and port_a == port_b and db_a == db_b


def test_is_same_postgres_database_identity_unit():
    """Unit test collision detection with pooler normalization, ports, and users."""
    url1 = (
        "postgresql://user:pass@ep-test-123-pooler.us-east-2.aws.neon.tech:5432/neondb"
    )
    url2 = "postgresql://user:pass2@ep-test-123.us-east-2.aws.neon.tech/neondb"
    assert is_same_postgres_database_identity(url1, url2) is True

    # Different user/password on same host/db is still collision True
    url_diff_user = (
        "postgresql://other_user:secret@ep-test-123.us-east-2.aws.neon.tech:5432/neondb"
    )
    assert is_same_postgres_database_identity(url1, url_diff_user) is True

    # Different database is False
    url_diff_db = (
        "postgresql://user:pass@ep-test-123.us-east-2.aws.neon.tech:5432/otherdb"
    )
    assert is_same_postgres_database_identity(url1, url_diff_db) is False

    # Different host is False
    url_diff_host = (
        "postgresql://user:pass@ep-other-456.us-east-2.aws.neon.tech:5432/neondb"
    )
    assert is_same_postgres_database_identity(url1, url_diff_host) is False


def test_postgres_url_composition_preserves_password_and_options():
    """Pure unit test proving URL composition preserves password and query params."""
    raw = (
        "postgresql://test_user:p%40ssw0rd_secret@ep-test-123456-pooler.us-east-2.aws.neon.tech:5432/"
        "neondb?sslmode=require&channel_binding=prefer"
    )
    parsed = make_url(raw)

    host = parsed.host or ""
    if "-pooler" in host:
        parsed = parsed.set(host=host.replace("-pooler", ""))

    query_dict = dict(parsed.query)
    query_dict["options"] = "-cstatement_timeout=30000 -clock_timeout=10000"
    query_dict["application_name"] = "equiped_mig_test"
    query_dict["connect_timeout"] = "10"

    schema_url_obj = parsed.set(query=query_dict)
    rendered = schema_url_obj.render_as_string(hide_password=False)

    assert schema_url_obj.password == "p@ssw0rd_secret"
    assert "p%40ssw0rd_secret" in rendered or "p@ssw0rd_secret" in rendered
    assert "sslmode=require" in rendered
    assert "channel_binding=prefer" in rendered
    assert (
        "statement_timeout%3D30000" in rendered or "statement_timeout=30000" in rendered
    )
    assert "lock_timeout%3D10000" in rendered or "lock_timeout=10000" in rendered
    assert schema_url_obj.host is not None and "-pooler" not in schema_url_obj.host


def _assert_fails_constraint(
    conn: Any,
    stmt: Any,
    params: dict[str, Any] | None = None,
    exc_type: type[Exception] = IntegrityError,
    match: str | None = None,
) -> None:
    """Execute a statement in a savepoint, assert failure, and rollback."""
    sp = conn.begin_nested()
    try:
        with pytest.raises(exc_type, match=match):
            conn.execute(stmt, params or {})
    finally:
        sp.rollback()


def test_single_alembic_head_and_down_revision():
    """Verify single linear Alembic migration head with correct down_revision."""
    from alembic.script import ScriptDirectory

    config = Config(str(REPO_ROOT / "server" / "alembic.ini"))
    script_dir = ScriptDirectory.from_config(config)
    heads = script_dir.get_heads()
    assert len(heads) == 1
    assert heads[0] == "20260829_0006"

    rev_0004 = script_dir.get_revision(TARGET_REVISION)
    assert rev_0004 is not None
    assert rev_0004.down_revision == DOWN_REVISION

    rev_0005 = script_dir.get_revision("20260829_0005")
    assert rev_0005 is not None
    assert rev_0005.down_revision == TARGET_REVISION

    rev_0006 = script_dir.get_revision("20260829_0006")
    assert rev_0006 is not None
    assert rev_0006.down_revision == "20260829_0005"


def test_downgrade_unconditionally_raises_runtime_error():
    """Downgrade must refuse execution and raise RuntimeError."""
    mig_mod = importlib.import_module(
        "server.alembic.versions.20260829_0004_dynamic_cid_forms"
    )

    with pytest.raises(RuntimeError, match="Downgrade is not supported"):
        mig_mod.downgrade()


def _seed_prior_schema_sqlite(conn) -> None:
    """Create synthetic schema as of 20260829_0003 for offline SQLite tests."""
    conn.execute(
        text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)")
    )
    conn.execute(text(f"INSERT INTO alembic_version VALUES ('{DOWN_REVISION}')"))

    conn.execute(
        text(
            "CREATE TABLE users ("
            "user_id TEXT PRIMARY KEY, email TEXT NOT NULL, "
            "name TEXT NOT NULL, password_hash TEXT NOT NULL, "
            "role TEXT NOT NULL, created_at DATETIME NOT NULL)"
        )
    )
    conn.execute(
        text(
            "CREATE TABLE documents ("
            "document_id TEXT PRIMARY KEY, title TEXT NOT NULL, "
            "filename TEXT NOT NULL, file_path TEXT NOT NULL, "
            "file_size_bytes INTEGER NOT NULL, status TEXT NOT NULL, "
            "created_at DATETIME NOT NULL)"
        )
    )
    conn.execute(
        text(
            "CREATE TABLE evaluation_jobs ("
            "evaluation_id TEXT PRIMARY KEY, document_id TEXT NOT NULL, "
            "status TEXT NOT NULL, created_at DATETIME NOT NULL)"
        )
    )
    conn.execute(
        text(
            "CREATE TABLE agent_results ("
            "agent_result_id TEXT PRIMARY KEY, evaluation_id TEXT NOT NULL, "
            "document_id TEXT NOT NULL, agent_name TEXT NOT NULL, "
            "subtotal FLOAT NOT NULL, processing_seconds FLOAT NOT NULL, "
            "token_count INTEGER NOT NULL, model_name TEXT NOT NULL, "
            "summary TEXT NOT NULL, success BOOLEAN NOT NULL, "
            "created_at DATETIME NOT NULL)"
        )
    )
    conn.execute(
        text(
            "CREATE TABLE rubric_sets ("
            "rubric_set_id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, "
            "name TEXT NOT NULL, version_number INTEGER NOT NULL, "
            "status TEXT NOT NULL, created_at DATETIME NOT NULL)"
        )
    )
    conn.execute(
        text(
            "CREATE TABLE rubric_domains ("
            "rubric_domain_id TEXT PRIMARY KEY, rubric_set_id TEXT NOT NULL, "
            "code TEXT NOT NULL, title TEXT NOT NULL, "
            "display_order INTEGER NOT NULL)"
        )
    )
    conn.execute(
        text(
            "CREATE TABLE rubric_criteria ("
            "rubric_criterion_id TEXT PRIMARY KEY, "
            "rubric_domain_id TEXT NOT NULL, criterion_code TEXT NOT NULL, "
            "title TEXT NOT NULL, description TEXT NOT NULL, "
            "scoring_rule TEXT, display_order INTEGER NOT NULL)"
        )
    )


def _seed_valid_populated_rubrics_sqlite(conn) -> dict[str, str]:
    """Seed complete valid legacy rubric sets for SQLite tests."""
    sme_id = str(uuid.uuid4())
    coord_id = str(uuid.uuid4())
    gad_id = str(uuid.uuid4())
    itso_id = str(uuid.uuid4())

    sme_dom1_id = str(uuid.uuid4())
    sme_dom2_id = str(uuid.uuid4())
    coord_dom_id = str(uuid.uuid4())
    gad_dom_id = str(uuid.uuid4())
    itso_dom_id = str(uuid.uuid4())

    conn.execute(
        text(
            "INSERT INTO rubric_sets VALUES "
            f"('{sme_id}', 'sme', 'SME Rubric v1', 1, 'active', '2026-01-01 00:00:00'),"
            f"('{coord_id}', 'coordinator', 'Coordinator v1', 1, 'active', "
            "'2026-01-01 00:00:00'),"
            f"('{gad_id}', 'gad', 'GAD Rubric v1', 1, 'active', "
            "'2026-01-01 00:00:00'),"
            f"('{itso_id}', 'itso', 'ITSO Rubric v1', 1, 'active', "
            "'2026-01-01 00:00:00')"
        )
    )
    conn.execute(
        text(
            "INSERT INTO rubric_domains VALUES "
            f"('{sme_dom1_id}', '{sme_id}', 'OP', 'Organization', 1),"
            f"('{sme_dom2_id}', '{sme_id}', 'A', 'Assessment', 2),"
            f"('{coord_dom_id}', '{coord_id}', 'OP', 'Coord Org', 1),"
            f"('{gad_dom_id}', '{gad_id}', 'GAD', 'Gender', 1),"
            f"('{itso_dom_id}', '{itso_id}', 'ITSO', 'ITSO Area', 1)"
        )
    )

    sme_codes = [
        "OP-01",
        "OP-02",
        "OP-03",
        "OP-04",
        "OP-05",
        "A-01",
        "A-02",
        "A-03",
        "A-04",
        "A-05",
    ]
    for i, code in enumerate(sme_codes):
        dom_id = sme_dom1_id if code.startswith("OP") else sme_dom2_id
        conn.execute(
            text(
                "INSERT INTO rubric_criteria VALUES "
                f"('{uuid.uuid4()}', '{dom_id}', '{code}', 'Title {code}', "
                f"'Desc {code}', 'Rule {code}', {i + 1})"
            )
        )

    gad_codes = ["GAD-01", "GAD-02", "GAD-03", "GAD-04", "GAD-05"]
    for i, code in enumerate(gad_codes):
        conn.execute(
            text(
                "INSERT INTO rubric_criteria VALUES "
                f"('{uuid.uuid4()}', '{gad_dom_id}', '{code}', 'Title {code}', "
                f"'Desc {code}', 'Rule {code}', {i + 1})"
            )
        )

    itso_codes = ["ITSO-01", "ITSO-02", "ITSO-03", "ITSO-04", "ITSO-05"]
    for i, code in enumerate(itso_codes):
        conn.execute(
            text(
                "INSERT INTO rubric_criteria VALUES "
                f"('{uuid.uuid4()}', '{itso_dom_id}', '{code}', 'Title {code}', "
                f"'Proper guidance for {code}', NULL, {i + 1})"
            )
        )

    return {
        "sme_id": sme_id,
        "coord_id": coord_id,
        "gad_id": gad_id,
        "itso_id": itso_id,
    }


def test_migration_upgrade_populated_sqlite(tmp_path):
    """Upgrade migrates active->published, backfills configs, creates coord v2."""
    db_path = tmp_path / "test_mig_populated.db"
    url = f"sqlite+pysqlite:///{db_path}"
    engine = create_engine(url)

    with engine.begin() as conn:
        _seed_prior_schema_sqlite(conn)
        ids = _seed_valid_populated_rubrics_sqlite(conn)

    _run(command.upgrade, _config(url), TARGET_REVISION)

    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        assert ctx.get_current_revision() == TARGET_REVISION

        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "rubric_agent_activations" in tables
        assert "evaluation_form_snapshots" in tables

        # Status active -> published
        sme_status = conn.execute(
            text(
                "SELECT status, adapter_key, adapter_version "
                f"FROM rubric_sets WHERE rubric_set_id = '{ids['sme_id']}'"
            )
        ).fetchone()
        assert sme_status is not None
        assert sme_status[0] == "published"
        assert sme_status[1] == "sme"
        assert sme_status[2] == 1

        # Coordinator v1 retired
        coord_status = conn.execute(
            text(
                "SELECT status FROM rubric_sets "
                f"WHERE rubric_set_id = '{ids['coord_id']}'"
            )
        ).scalar()
        assert coord_status == "retired"

        # Coordinator v2 created & published
        coord_v2 = conn.execute(
            text(
                "SELECT rubric_set_id, status, version_number "
                "FROM rubric_sets "
                "WHERE agent_id = 'coordinator' AND version_number = 2"
            )
        ).fetchone()
        assert coord_v2 is not None
        assert coord_v2[1] == "published"

        # Activations populated for all 4 agents
        activations = conn.execute(
            text("SELECT agent_id, rubric_set_id FROM rubric_agent_activations")
        ).fetchall()
        act_map = {row[0]: row[1] for row in activations}
        assert set(act_map.keys()) == {"sme", "gad", "itso", "coordinator"}
        assert uuid.UUID(str(act_map["sme"])) == uuid.UUID(str(ids["sme_id"]))
        assert uuid.UUID(str(act_map["gad"])) == uuid.UUID(str(ids["gad_id"]))
        assert uuid.UUID(str(act_map["itso"])) == uuid.UUID(str(ids["itso_id"]))
        assert uuid.UUID(str(act_map["coordinator"])) == uuid.UUID(str(coord_v2[0]))

    engine.dispose()


def test_migration_upgrade_no_row_fresh_schema(tmp_path):
    """Upgrade on empty database succeeds without errors and creates tables."""
    db_path = tmp_path / "test_mig_empty.db"
    url = f"sqlite+pysqlite:///{db_path}"
    engine = create_engine(url)

    with engine.begin() as conn:
        _seed_prior_schema_sqlite(conn)

    _run(command.upgrade, _config(url), TARGET_REVISION)

    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        assert ctx.get_current_revision() == TARGET_REVISION

        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "rubric_agent_activations" in tables
        assert "evaluation_form_snapshots" in tables

    engine.dispose()


def test_migration_preflight_fails_on_missing_active_candidate(tmp_path):
    """Preflight fails atomically if an agent has no active candidate."""
    db_path = tmp_path / "test_mig_missing_active.db"
    url = f"sqlite+pysqlite:///{db_path}"
    engine = create_engine(url)

    with engine.begin() as conn:
        _seed_prior_schema_sqlite(conn)
        _seed_valid_populated_rubrics_sqlite(conn)
        # Delete active GAD row
        conn.execute(text("DELETE FROM rubric_sets WHERE agent_id = 'gad'"))

    with pytest.raises(RuntimeError, match="Migration preflight failed"):
        _run(command.upgrade, _config(url), TARGET_REVISION)

    engine.dispose()


def test_migration_preflight_fails_on_ambiguous_active_candidate(tmp_path):
    """Preflight fails atomically if an agent has >1 active candidate."""
    db_path = tmp_path / "test_mig_ambiguous_active.db"
    url = f"sqlite+pysqlite:///{db_path}"
    engine = create_engine(url)

    with engine.begin() as conn:
        _seed_prior_schema_sqlite(conn)
        _seed_valid_populated_rubrics_sqlite(conn)
        # Insert duplicate active SME set
        conn.execute(
            text(
                "INSERT INTO rubric_sets VALUES "
                f"('{uuid.uuid4()}', 'sme', 'SME Dup', 2, "
                "'active', '2026-01-01 00:00:00')"
            )
        )

    with pytest.raises(RuntimeError, match="Migration preflight failed"):
        _run(command.upgrade, _config(url), TARGET_REVISION)

    engine.dispose()


def test_migration_preflight_fails_on_mismatched_criteria_codes(tmp_path):
    """Preflight fails if active set criteria codes do not match manifest."""
    db_path = tmp_path / "test_mig_bad_criteria.db"
    url = f"sqlite+pysqlite:///{db_path}"
    engine = create_engine(url)

    with engine.begin() as conn:
        _seed_prior_schema_sqlite(conn)
        _seed_valid_populated_rubrics_sqlite(conn)
        # Mutate SME criterion code
        conn.execute(
            text(
                "UPDATE rubric_criteria SET criterion_code = 'OP-99' "
                "WHERE criterion_code = 'OP-01'"
            )
        )

    with pytest.raises(RuntimeError, match="SME active criteria mismatch"):
        _run(command.upgrade, _config(url), TARGET_REVISION)

    engine.dispose()


def test_migration_preflight_fails_on_duplicate_criterion_cross_domain(tmp_path):
    """Preflight fails if an expected criterion code is duplicated in another domain."""
    db_path = tmp_path / "test_mig_dup_criterion.db"
    url = f"sqlite+pysqlite:///{db_path}"
    engine = create_engine(url)

    with engine.begin() as conn:
        _seed_prior_schema_sqlite(conn)
        _seed_valid_populated_rubrics_sqlite(conn)
        # Get SME domain 'A' and insert duplicate OP-01
        dom_a_id = conn.execute(
            text(
                "SELECT rd.rubric_domain_id FROM rubric_domains rd "
                "JOIN rubric_sets rs ON rs.rubric_set_id = rd.rubric_set_id "
                "WHERE rs.agent_id = 'sme' AND rd.code = 'A'"
            )
        ).scalar()
        conn.execute(
            text(
                "INSERT INTO rubric_criteria VALUES "
                f"('{uuid.uuid4()}', '{dom_a_id}', 'OP-01', "
                "'Duplicate OP-01 in Domain A', 'Desc', 'Rule', 99)"
            )
        )

    with pytest.raises(RuntimeError, match="SME active criteria"):
        _run(command.upgrade, _config(url), TARGET_REVISION)

    engine.dispose()


def test_migration_preflight_fails_on_blank_set_name(tmp_path):
    """Preflight fails if active set name is blank."""
    db_path = tmp_path / "test_mig_blank_name.db"
    url = f"sqlite+pysqlite:///{db_path}"
    engine = create_engine(url)

    with engine.begin() as conn:
        _seed_prior_schema_sqlite(conn)
        _seed_valid_populated_rubrics_sqlite(conn)
        conn.execute(text("UPDATE rubric_sets SET name = '   ' WHERE agent_id = 'sme'"))

    with pytest.raises(RuntimeError, match="invalid name"):
        _run(command.upgrade, _config(url), TARGET_REVISION)

    engine.dispose()


def test_migration_preflight_fails_on_nonpositive_version(tmp_path):
    """Preflight fails if active set version_number is <= 0."""
    db_path = tmp_path / "test_mig_bad_version.db"
    url = f"sqlite+pysqlite:///{db_path}"
    engine = create_engine(url)

    with engine.begin() as conn:
        _seed_prior_schema_sqlite(conn)
        _seed_valid_populated_rubrics_sqlite(conn)
        conn.execute(
            text("UPDATE rubric_sets SET version_number = 0 WHERE agent_id = 'sme'")
        )

    with pytest.raises(RuntimeError, match="non-positive version"):
        _run(command.upgrade, _config(url), TARGET_REVISION)

    engine.dispose()


def test_migration_preflight_fails_on_empty_domain(tmp_path):
    """Preflight fails if an active set contains a domain with no criteria."""
    db_path = tmp_path / "test_mig_empty_domain.db"
    url = f"sqlite+pysqlite:///{db_path}"
    engine = create_engine(url)

    with engine.begin() as conn:
        _seed_prior_schema_sqlite(conn)
        ids = _seed_valid_populated_rubrics_sqlite(conn)
        # Insert an empty domain into active SME set
        conn.execute(
            text(
                "INSERT INTO rubric_domains VALUES "
                f"('{uuid.uuid4()}', '{ids['sme_id']}', 'EXTRA', 'Empty Domain', 99)"
            )
        )

    with pytest.raises(RuntimeError, match="domain without criteria"):
        _run(command.upgrade, _config(url), TARGET_REVISION)

    engine.dispose()


def test_migration_preflight_fails_on_whitespace_scoring_rule(tmp_path):
    """Preflight fails if criterion scoring_rule is non-null but whitespace."""
    db_path = tmp_path / "test_mig_ws_rule.db"
    url = f"sqlite+pysqlite:///{db_path}"
    engine = create_engine(url)

    with engine.begin() as conn:
        _seed_prior_schema_sqlite(conn)
        _seed_valid_populated_rubrics_sqlite(conn)
        conn.execute(
            text(
                "UPDATE rubric_criteria SET scoring_rule = '   ' "
                "WHERE criterion_code = 'OP-01'"
            )
        )

    with pytest.raises(RuntimeError, match="scoring_rule is blank"):
        _run(command.upgrade, _config(url), TARGET_REVISION)

    engine.dispose()


# ---------------------------------------------------------------------------
# Opt-In PostgreSQL Migration Test against Disposable Database
# ---------------------------------------------------------------------------


def _postgres_test_skip_reason() -> str | None:
    flag = os.environ.get(POSTGRES_MIGRATION_FLAG, "").strip()
    if flag != "1":
        return (
            f"{POSTGRES_MIGRATION_FLAG} != '1'; "
            "skipping isolated PostgreSQL migration test"
        )
    disp = os.environ.get(DISPOSABLE_FLAG, "").strip()
    if disp != "YES":
        return (
            f"{DISPOSABLE_FLAG} != 'YES'; skipping isolated PostgreSQL migration test"
        )
    raw_url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if not raw_url:
        return "TEST_DATABASE_URL not set; skipping isolated PostgreSQL migration test"
    return None


@pytest.mark.skipif(
    _postgres_test_skip_reason() is not None,
    reason=_postgres_test_skip_reason() or "Skipping PostgreSQL test",
)
def test_postgres_migration_disposable_database():
    """Opt-in PG migration test on disposable DB branch at 20260829_0003."""
    skip_reason = _postgres_test_skip_reason()
    if skip_reason:
        pytest.skip(skip_reason)

    raw_url = os.environ["TEST_DATABASE_URL"].strip()
    parsed_url = make_url(raw_url)

    if parsed_url.get_backend_name() != "postgresql":
        pytest.fail(
            f"TEST_DATABASE_URL must be postgresql, got {parsed_url.get_backend_name()}"
        )

    # Collision prevention against application database identity
    app_db_url_str = os.environ.get("DATABASE_URL", "").strip()
    from server.core.config import get_settings

    settings = get_settings()
    configured_db_url = (settings.database_url or "").strip()

    for candidate in (app_db_url_str, configured_db_url):
        if candidate and is_same_postgres_database_identity(candidate, raw_url):
            pytest.fail("TEST_DATABASE_URL targets the configured application database")

    # Neon direct endpoint conversion if pooler host
    host = parsed_url.host or ""
    if "-pooler" in host:
        direct_host = host.replace("-pooler", "")
        parsed_url = parsed_url.set(host=direct_host)

    query_dict = dict(parsed_url.query)
    query_dict["options"] = "-cstatement_timeout=30000 -clock_timeout=10000"
    query_dict["application_name"] = "equiped_mig_test"
    query_dict["connect_timeout"] = "10"

    target_url_obj = parsed_url.set(query=query_dict)
    target_url = target_url_obj.render_as_string(hide_password=False)
    engine = create_engine(target_url)

    try:
        # 1. Assert pre-migration DB identity and DOWN_REVISION (20260829_0003)
        expected_db = (parsed_url.database or "").lstrip("/")
        with engine.connect() as conn:
            actual_db = conn.execute(text("SELECT current_database()")).scalar()
            assert actual_db == expected_db, (
                f"Expected database '{expected_db}', got '{actual_db}'"
            )

            ctx = MigrationContext.configure(conn)
            current_rev = ctx.get_current_revision()
            assert current_rev == DOWN_REVISION, (
                f"Disposable DB must be stamped at {DOWN_REVISION}, got {current_rev}"
            )

            # Capture exact active candidate IDs from the disposable database
            sme_active = conn.execute(
                text(
                    "SELECT rubric_set_id FROM rubric_sets "
                    "WHERE agent_id = 'sme' AND status = 'active'"
                )
            ).fetchall()
            coord_active = conn.execute(
                text(
                    "SELECT rubric_set_id FROM rubric_sets "
                    "WHERE agent_id = 'coordinator' AND status = 'active'"
                )
            ).fetchall()
            gad_active = conn.execute(
                text(
                    "SELECT rubric_set_id FROM rubric_sets "
                    "WHERE agent_id = 'gad' AND status = 'active'"
                )
            ).fetchall()
            itso_active = conn.execute(
                text(
                    "SELECT rubric_set_id FROM rubric_sets "
                    "WHERE agent_id = 'itso' AND status = 'active'"
                )
            ).fetchall()

            assert len(sme_active) == 1, (
                f"Expected 1 active SME rubric, got {len(sme_active)}"
            )
            assert len(coord_active) == 1, (
                f"Expected 1 active Coord rubric, got {len(coord_active)}"
            )
            assert len(gad_active) == 1, (
                f"Expected 1 active GAD rubric, got {len(gad_active)}"
            )
            assert len(itso_active) == 1, (
                f"Expected 1 active ITSO rubric, got {len(itso_active)}"
            )

            active_sme_id = sme_active[0][0]
            active_coord_id = coord_active[0][0]
            active_gad_id = gad_active[0][0]
            active_itso_id = itso_active[0][0]

        # 2. Run ONLY forward migration to TARGET_REVISION
        _run(command.upgrade, _config(target_url), TARGET_REVISION)

        # 3. Comprehensive post-upgrade assertions on PostgreSQL
        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            assert ctx.get_current_revision() == TARGET_REVISION

            inspector = inspect(engine)
            tables = inspector.get_table_names()
            assert "rubric_agent_activations" in tables
            assert "evaluation_form_snapshots" in tables

            # Complete exact criterion scoring_strategy and strategy_config maps
            sme_rows = conn.execute(
                text(
                    "SELECT rc.criterion_code, rc.scoring_strategy, "
                    "rc.strategy_config "
                    "FROM rubric_criteria rc "
                    "JOIN rubric_domains rd "
                    "ON rd.rubric_domain_id = rc.rubric_domain_id "
                    "WHERE rd.rubric_set_id = :set_id"
                ).bindparams(sa.bindparam("set_id", type_=sa.Uuid(as_uuid=True))),
                {"set_id": active_sme_id},
            ).fetchall()
            assert len(sme_rows) == len(_SME_STRATEGY_CONFIGS)
            sme_map = {r[0]: (r[1], r[2]) for r in sme_rows}
            for code, expected_cfg in _SME_STRATEGY_CONFIGS.items():
                strat, cfg = sme_map[code]
                assert strat == expected_cfg["strategy"]
                assert cfg == expected_cfg

            gad_rows = conn.execute(
                text(
                    "SELECT rc.criterion_code, rc.scoring_strategy, "
                    "rc.strategy_config "
                    "FROM rubric_criteria rc "
                    "JOIN rubric_domains rd "
                    "ON rd.rubric_domain_id = rc.rubric_domain_id "
                    "WHERE rd.rubric_set_id = :set_id"
                ).bindparams(sa.bindparam("set_id", type_=sa.Uuid(as_uuid=True))),
                {"set_id": active_gad_id},
            ).fetchall()
            assert len(gad_rows) == len(_GAD_STRATEGY_CONFIGS)
            gad_map = {r[0]: (r[1], r[2]) for r in gad_rows}
            for code, expected_cfg in _GAD_STRATEGY_CONFIGS.items():
                strat, cfg = gad_map[code]
                assert strat == expected_cfg["strategy"]
                assert cfg == expected_cfg

            itso_rows = conn.execute(
                text(
                    "SELECT rc.criterion_code, rc.scoring_strategy, "
                    "rc.strategy_config, rc.description "
                    "FROM rubric_criteria rc "
                    "JOIN rubric_domains rd "
                    "ON rd.rubric_domain_id = rc.rubric_domain_id "
                    "WHERE rd.rubric_set_id = :set_id"
                ).bindparams(sa.bindparam("set_id", type_=sa.Uuid(as_uuid=True))),
                {"set_id": active_itso_id},
            ).fetchall()
            assert len(itso_rows) == 5
            assert {row[0] for row in itso_rows} == {
                "ITSO-01",
                "ITSO-02",
                "ITSO-03",
                "ITSO-04",
                "ITSO-05",
            }
            for code, strat, cfg, desc in itso_rows:
                assert strat == "llm_rubric_guidance"
                assert cfg == {"strategy": "llm_rubric_guidance", "guidance": desc}

            # Coordinator v1 retired, Coordinator v2 published & active
            coord_v1_status = conn.execute(
                text(
                    "SELECT status FROM rubric_sets WHERE rubric_set_id = :id"
                ).bindparams(sa.bindparam("id", type_=sa.Uuid(as_uuid=True))),
                {"id": active_coord_id},
            ).scalar()
            assert coord_v1_status == "retired"

            coord_v2 = conn.execute(
                text(
                    "SELECT rubric_set_id, status, version_number "
                    "FROM rubric_sets "
                    "WHERE agent_id = 'coordinator' AND version_number = 2"
                )
            ).fetchone()
            assert coord_v2 is not None
            assert coord_v2[1] == "published"

            coord_v2_domain_count = conn.execute(
                text(
                    "SELECT COUNT(*) FROM rubric_domains WHERE rubric_set_id = :set_id"
                ).bindparams(sa.bindparam("set_id", type_=sa.Uuid(as_uuid=True))),
                {"set_id": coord_v2[0]},
            ).scalar_one()
            assert coord_v2_domain_count == 1

            # Coordinator v2 criteria assertions (1 domain, 1 criterion A-05)
            coord_v2_crit = conn.execute(
                text(
                    "SELECT rc.criterion_code, rc.scoring_strategy, "
                    "rc.strategy_config "
                    "FROM rubric_criteria rc "
                    "JOIN rubric_domains rd "
                    "ON rd.rubric_domain_id = rc.rubric_domain_id "
                    "WHERE rd.rubric_set_id = :set_id"
                ).bindparams(sa.bindparam("set_id", type_=sa.Uuid(as_uuid=True))),
                {"set_id": coord_v2[0]},
            ).fetchall()
            assert len(coord_v2_crit) == 1
            assert coord_v2_crit[0][0] == "A-05"
            assert coord_v2_crit[0][1] == "curriculum_alignment"
            assert coord_v2_crit[0][2] == {"strategy": "curriculum_alignment"}

            # Activations
            activations = conn.execute(
                text("SELECT agent_id, rubric_set_id FROM rubric_agent_activations")
            ).fetchall()
            act_map = {row[0]: row[1] for row in activations}
            assert act_map["sme"] == active_sme_id
            assert act_map["gad"] == active_gad_id
            assert act_map["itso"] == active_itso_id
            assert act_map["coordinator"] == coord_v2[0]

            # Schema inspections: nullability, FKs, constraints, indexes
            cols = {c["name"]: c for c in inspector.get_columns("rubric_sets")}
            assert cols["adapter_key"]["nullable"] is False

            # Check rubric_sets foreign keys
            rs_fks = {
                (
                    tuple(fk["constrained_columns"]),
                    fk["referred_table"],
                    tuple(fk["referred_columns"]),
                ): fk
                for fk in inspector.get_foreign_keys("rubric_sets")
            }
            for col_name in ("published_by", "created_by", "retired_by"):
                key = ((col_name,), "users", ("user_id",))
                assert key in rs_fks
                assert rs_fks[key].get("options", {}).get("ondelete") == "SET NULL"

            # Check rubric_agent_activations foreign keys
            act_fks = {
                (
                    tuple(fk["constrained_columns"]),
                    fk["referred_table"],
                    tuple(fk["referred_columns"]),
                ): fk
                for fk in inspector.get_foreign_keys("rubric_agent_activations")
            }
            updated_by_key = (("updated_by",), "users", ("user_id",))
            assert updated_by_key in act_fks
            assert (
                act_fks[updated_by_key].get("options", {}).get("ondelete", "").upper()
                == "SET NULL"
            )
            assert (
                ("agent_id", "rubric_set_id"),
                "rubric_sets",
                ("agent_id", "rubric_set_id"),
            ) in act_fks

            # Check check constraints on rubric_sets
            ck_names = [
                ck["name"] for ck in inspector.get_check_constraints("rubric_sets")
            ]
            assert "ck_rubric_sets_status" in ck_names

            # Check indexes on rubric_sets
            idx_map = {idx["name"]: idx for idx in inspector.get_indexes("rubric_sets")}
            assert "uq_rubric_sets_one_draft_per_agent" in idx_map
            draft_index = idx_map["uq_rubric_sets_one_draft_per_agent"]
            assert draft_index["unique"] is True
            draft_predicate = str(
                draft_index.get("dialect_options", {}).get("postgresql_where", "")
            ).lower()
            assert "status" in draft_predicate and "draft" in draft_predicate

            # Check evaluation_form_snapshots foreign keys & unique
            snap_fks = {
                (
                    tuple(fk["constrained_columns"]),
                    fk["referred_table"],
                    tuple(fk["referred_columns"]),
                )
                for fk in inspector.get_foreign_keys("evaluation_form_snapshots")
            }
            assert (
                ("evaluation_id",),
                "evaluation_jobs",
                ("evaluation_id",),
            ) in snap_fks
            assert (("rubric_set_id",), "rubric_sets", ("rubric_set_id",)) in snap_fks

            snap_uniques = [
                tuple(u["column_names"])
                for u in inspector.get_unique_constraints("evaluation_form_snapshots")
            ]
            assert ("evaluation_id", "agent_id") in snap_uniques

            # Check agent_results form_snapshot_id FK
            ar_fks = {
                (
                    tuple(fk["constrained_columns"]),
                    fk["referred_table"],
                    tuple(fk["referred_columns"]),
                )
                for fk in inspector.get_foreign_keys("agent_results")
            }
            assert (
                ("form_snapshot_id",),
                "evaluation_form_snapshots",
                ("snapshot_id",),
            ) in ar_fks

            # Check PostgreSQL trigger existence and status
            trg_row = conn.execute(
                text(
                    "SELECT t.tgname, t.tgenabled FROM pg_trigger t "
                    "JOIN pg_class c ON c.oid = t.tgrelid "
                    "JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE t.tgname = 'trg_evaluation_form_snapshots_immutable' "
                    "AND c.relname = 'evaluation_form_snapshots' "
                    "AND n.nspname = current_schema()"
                )
            ).fetchone()
            assert trg_row is not None
            assert trg_row[1] in ("O", "A", True, "t")

            # Composite same-agent FK enforcement
            _assert_fails_constraint(
                conn,
                text(
                    "INSERT INTO rubric_agent_activations "
                    "(agent_id, rubric_set_id, updated_by, updated_at) "
                    "VALUES ('gad', :sme_id, NULL, NOW())"
                ).bindparams(sa.bindparam("sme_id", type_=sa.Uuid(as_uuid=True))),
                {"sme_id": active_sme_id},
                IntegrityError,
            )

            # One-draft-per-agent partial unique index enforcement
            draft1_id = uuid.uuid4()
            conn.execute(
                text(
                    "INSERT INTO rubric_sets "
                    "(rubric_set_id, agent_id, name, version_number, "
                    "status, adapter_key, created_at) "
                    "VALUES (:id, 'sme', 'SME Draft 1', 2, "
                    "'draft', 'sme', NOW())"
                ).bindparams(sa.bindparam("id", type_=sa.Uuid(as_uuid=True))),
                {"id": draft1_id},
            )
            _assert_fails_constraint(
                conn,
                text(
                    "INSERT INTO rubric_sets "
                    "(rubric_set_id, agent_id, name, version_number, "
                    "status, adapter_key, created_at) "
                    "VALUES (:id, 'sme', 'SME Draft 2', 3, "
                    "'draft', 'sme', NOW())"
                ).bindparams(sa.bindparam("id", type_=sa.Uuid(as_uuid=True))),
                {"id": uuid.uuid4()},
                IntegrityError,
            )

            # Status CHECK constraint enforcement
            _assert_fails_constraint(
                conn,
                text(
                    "INSERT INTO rubric_sets "
                    "(rubric_set_id, agent_id, name, version_number, "
                    "status, adapter_key, created_at) "
                    "VALUES (:id, 'itso', 'Invalid Status', 2, "
                    "'invalid_status', 'itso', NOW())"
                ).bindparams(sa.bindparam("id", type_=sa.Uuid(as_uuid=True))),
                {"id": uuid.uuid4()},
                IntegrityError,
            )

        # 4. Seed valid snapshot and test DB immutability triggers
        user_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        eval_id = uuid.uuid4()
        snap_id = uuid.uuid4()

        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO users "
                    "(user_id, email, name, password_hash, role, created_at) "
                    "VALUES (:uid, 'u@example.com', 'User', 'hash', 'admin', NOW())"
                ).bindparams(sa.bindparam("uid", type_=sa.Uuid(as_uuid=True))),
                {"uid": user_id},
            )
            conn.execute(
                text(
                    "INSERT INTO documents "
                    "(document_id, title, source_type, file_path, "
                    "uploaded_by, uploaded_at) "
                    "VALUES (:did, 'Title', 'slm', '/tmp/f.pdf', :uid, NOW())"
                ).bindparams(
                    sa.bindparam("did", type_=sa.Uuid(as_uuid=True)),
                    sa.bindparam("uid", type_=sa.Uuid(as_uuid=True)),
                ),
                {"did": doc_id, "uid": user_id},
            )
            conn.execute(
                text(
                    "INSERT INTO evaluation_jobs "
                    "(evaluation_id, document_id, status, submitted_at, submitted_by) "
                    "VALUES (:eid, :did, 'EVALUATING', NOW(), :uid)"
                ).bindparams(
                    sa.bindparam("eid", type_=sa.Uuid(as_uuid=True)),
                    sa.bindparam("did", type_=sa.Uuid(as_uuid=True)),
                    sa.bindparam("uid", type_=sa.Uuid(as_uuid=True)),
                ),
                {"eid": eval_id, "did": doc_id, "uid": user_id},
            )
            conn.execute(
                text(
                    "INSERT INTO evaluation_form_snapshots "
                    "(snapshot_id, evaluation_id, agent_id, rubric_set_id, "
                    "snapshot_payload, snapshot_hash, adapter_key, "
                    "adapter_version, created_at) "
                    "VALUES (:sid, :eid, 'sme', :rsid, '{\"k\": \"v\"}', "
                    "'hash64', 'sme', 1, NOW())"
                ).bindparams(
                    sa.bindparam("sid", type_=sa.Uuid(as_uuid=True)),
                    sa.bindparam("eid", type_=sa.Uuid(as_uuid=True)),
                    sa.bindparam("rsid", type_=sa.Uuid(as_uuid=True)),
                ),
                {"sid": snap_id, "eid": eval_id, "rsid": active_sme_id},
            )

        # Snapshot UNIQUE(evaluation_id, agent_id) constraint in savepoint
        with engine.connect() as conn:
            _assert_fails_constraint(
                conn,
                text(
                    "INSERT INTO evaluation_form_snapshots "
                    "(snapshot_id, evaluation_id, agent_id, "
                    "rubric_set_id, snapshot_payload, snapshot_hash, "
                    "adapter_key, adapter_version, created_at) "
                    "VALUES (:sid, :eid, 'sme', :rsid, "
                    "'{\"k2\": \"v2\"}', 'hash64_2', 'sme', 1, NOW())"
                ).bindparams(
                    sa.bindparam("sid", type_=sa.Uuid(as_uuid=True)),
                    sa.bindparam("eid", type_=sa.Uuid(as_uuid=True)),
                    sa.bindparam("rsid", type_=sa.Uuid(as_uuid=True)),
                ),
                {"sid": uuid.uuid4(), "eid": eval_id, "rsid": active_sme_id},
                IntegrityError,
            )

        # Test UPDATE refusal in a clean transaction
        with engine.connect() as conn:
            trans = conn.begin()
            try:
                conn.execute(
                    text(
                        "UPDATE evaluation_form_snapshots "
                        "SET adapter_version = 2 WHERE snapshot_id = :id"
                    ).bindparams(sa.bindparam("id", type_=sa.Uuid(as_uuid=True))),
                    {"id": snap_id},
                )
                pytest.fail("UPDATE on snapshots should fail")
            except (DatabaseError, InternalError) as exc:
                msg = str(exc).lower()
                assert "immutable" in msg
                assert "infailedsqltransaction" not in msg
            finally:
                trans.rollback()

        # Test DELETE refusal in a clean transaction
        with engine.connect() as conn:
            trans = conn.begin()
            try:
                conn.execute(
                    text(
                        "DELETE FROM evaluation_form_snapshots WHERE snapshot_id = :id"
                    ).bindparams(sa.bindparam("id", type_=sa.Uuid(as_uuid=True))),
                    {"id": snap_id},
                )
                pytest.fail("DELETE on snapshots should fail")
            except (DatabaseError, InternalError) as exc:
                msg = str(exc).lower()
                assert "immutable" in msg
                assert "infailedsqltransaction" not in msg
            finally:
                trans.rollback()

        # 5. Test Alembic downgrade refusal
        with pytest.raises(RuntimeError, match="Downgrade is not supported"):
            _run(command.downgrade, _config(target_url), DOWN_REVISION)

        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            assert ctx.get_current_revision() == TARGET_REVISION

    finally:
        engine.dispose()
