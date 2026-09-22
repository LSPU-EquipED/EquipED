"""Tests for 20260918_0002_backfill_legacy_syllabus_alignment migration."""

from __future__ import annotations

import importlib.util
import json
import os
import uuid
from pathlib import Path

from alembic.command import upgrade as alembic_upgrade
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = (
    REPO_ROOT
    / "alembic"
    / "versions"
    / "20260918_0002_backfill_legacy_syllabus_alignment.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "migration_20260918_0002", MIGRATION_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _config(database_url: str) -> Config:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _run_upgrade(database_url: str, revision: str = "20260918_0002") -> None:
    from server.core.config import get_settings

    config = _config(database_url)
    original = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = ""
    get_settings.cache_clear()
    try:
        alembic_upgrade(config, revision)
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
        conn.execute(text("INSERT INTO alembic_version VALUES ('20260918_0001')"))

        conn.execute(
            text(
                "CREATE TABLE users ("
                "user_id CHAR(36) PRIMARY KEY, "
                "email VARCHAR(255) NOT NULL"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE documents ("
                "document_id CHAR(36) PRIMARY KEY, "
                "title VARCHAR(255) NOT NULL"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE evaluation_jobs ("
                "evaluation_id CHAR(36) PRIMARY KEY, "
                "submitted_by CHAR(36) REFERENCES users(user_id), "
                "completed_at DATETIME"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE agent_results ("
                "agent_result_id CHAR(36) PRIMARY KEY, "
                "evaluation_id CHAR(36) REFERENCES evaluation_jobs(evaluation_id), "
                "document_id CHAR(36) REFERENCES documents(document_id), "
                "advisory_outputs JSON, "
                "created_at DATETIME NOT NULL"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE syllabus_alignment_runs ("
                "alignment_id CHAR(36) PRIMARY KEY, "
                "slm_document_id CHAR(36) NOT NULL REFERENCES documents(document_id), "
                "syllabus_document_id CHAR(36) NOT NULL "
                "REFERENCES documents(document_id), "
                "requested_by CHAR(36) NOT NULL REFERENCES users(user_id), "
                "status VARCHAR(20) NOT NULL, "
                "alignment_level VARCHAR(30), "
                "justification TEXT, "
                "alignment_artifact JSON, "
                "model_name VARCHAR(200), "
                "provenance JSON, "
                "error_message TEXT, "
                "created_at DATETIME NOT NULL, "
                "started_at DATETIME, "
                "completed_at DATETIME, "
                "updated_at DATETIME NOT NULL"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE UNIQUE INDEX uq_syllabus_alignment_slm "
                "ON syllabus_alignment_runs (slm_document_id)"
            )
        )


def test_migration_metadata():
    """Verify revision chain, down_revision, and alembic head consistency."""
    migration = _load_migration()
    assert migration.revision == "20260918_0002"
    assert migration.down_revision == "20260918_0001"

    config = _config("sqlite://")
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ["20260923_0001"]

    rev_0002 = script.get_revision("20260918_0002")
    assert rev_0002 is not None
    assert rev_0002.down_revision == "20260918_0001"


def test_no_source_rows_fresh_db(tmp_path):
    """Empty/fresh database with no agent_results completes cleanly."""
    db_path = tmp_path / f"fresh-{uuid.uuid4()}.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    engine = create_engine(db_url)
    _setup_test_database(engine)

    _run_upgrade(db_url)

    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT count(*) FROM syllabus_alignment_runs")
        ).scalar()
        assert count == 0


def test_valid_legacy_artifact_backfill(tmp_path):
    """Valid legacy advisory_outputs artifact is converted to syllabus run."""
    db_path = tmp_path / f"valid-{uuid.uuid4()}.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    engine = create_engine(db_url)
    _setup_test_database(engine)

    user_id = str(uuid.uuid4())
    slm_id = str(uuid.uuid4())
    syllabus_id = str(uuid.uuid4())
    eval_id = str(uuid.uuid4())
    result_id = str(uuid.uuid4())

    artifact = {
        "syllabus_document_id": syllabus_id,
        "status": "MEETS",
        "processing_state": "COMPLETED",
        "statement": "Course aligns well with syllabus requirements.",
    }

    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO users (user_id, email) VALUES (:uid, :email)"),
            {"uid": user_id, "email": "faculty@lspu.edu.ph"},
        )
        conn.execute(
            text("INSERT INTO documents (document_id, title) VALUES (:did, :title)"),
            [
                {"did": slm_id, "title": "Module 1 SLM"},
                {"did": syllabus_id, "title": "IT 101 Syllabus"},
            ],
        )
        insert_job_sql = (
            "INSERT INTO evaluation_jobs (evaluation_id, submitted_by, completed_at) "
            "VALUES (:eid, :uid, '2026-08-05 10:00:00')"
        )
        conn.execute(
            text(insert_job_sql),
            {"eid": eval_id, "uid": user_id},
        )
        insert_agent_sql = (
            "INSERT INTO agent_results "
            "(agent_result_id, evaluation_id, document_id, "
            "advisory_outputs, created_at) "
            "VALUES (:rid, :eid, :did, :advisory, '2026-08-05 09:30:00')"
        )
        conn.execute(
            text(insert_agent_sql),
            {
                "rid": result_id,
                "eid": eval_id,
                "did": slm_id,
                "advisory": json.dumps({"syllabus_alignment": artifact}),
            },
        )

    _run_upgrade(db_url)

    with engine.connect() as conn:
        rows = (
            conn.execute(text("SELECT * FROM syllabus_alignment_runs")).mappings().all()
        )
        assert len(rows) == 1
        row = rows[0]
        norm_slm = str(row["slm_document_id"]).replace("-", "")
        norm_syllabus = str(row["syllabus_document_id"]).replace("-", "")
        norm_user = str(row["requested_by"]).replace("-", "")
        assert norm_slm == slm_id.replace("-", "")
        assert norm_syllabus == syllabus_id.replace("-", "")
        assert norm_user == user_id.replace("-", "")
        assert row["status"] == "COMPLETED"
        assert row["alignment_level"] == "MEETS"
        assert row["justification"] == "Course aligns well with syllabus requirements."
        assert row["error_message"] is None
        raw_prov = row["provenance"]
        prov = json.loads(raw_prov) if isinstance(raw_prov, str) else raw_prov
        assert prov == {
            "legacy_source": "agent_results.advisory_outputs",
            "model_attribution": "unavailable",
        }


def test_invalid_or_missing_references_skipped(tmp_path):
    """Rows with missing references or malformed JSON are skipped."""
    db_path = tmp_path / f"invalid-{uuid.uuid4()}.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    engine = create_engine(db_url)
    _setup_test_database(engine)

    user_id = str(uuid.uuid4())
    slm_id = str(uuid.uuid4())
    syllabus_id = str(uuid.uuid4())
    unknown_syllabus_id = str(uuid.uuid4())

    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO users (user_id, email) VALUES (:uid, :email)"),
            {"uid": user_id, "email": "faculty@lspu.edu.ph"},
        )
        conn.execute(
            text("INSERT INTO documents (document_id, title) VALUES (:did, :title)"),
            [
                {"did": slm_id, "title": "Module 1 SLM"},
                {"did": syllabus_id, "title": "IT 101 Syllabus"},
            ],
        )

        insert_results_sql = (
            "INSERT INTO agent_results "
            "(agent_result_id, evaluation_id, document_id, "
            "advisory_outputs, created_at) "
            "VALUES (:rid, :eid, :did, :advisory, '2026-08-05 09:30:00')"
        )
        # 1. Job without submitted_by
        eval_id1 = str(uuid.uuid4())
        conn.execute(
            text(
                "INSERT INTO evaluation_jobs "
                "(evaluation_id, submitted_by, completed_at) "
                "VALUES (:eid, NULL, '2026-08-05 10:00:00')"
            ),
            {"eid": eval_id1},
        )
        conn.execute(
            text(insert_results_sql),
            {
                "rid": str(uuid.uuid4()),
                "eid": eval_id1,
                "did": slm_id,
                "advisory": json.dumps(
                    {
                        "syllabus_alignment": {
                            "syllabus_document_id": syllabus_id,
                            "status": "MEETS",
                            "processing_state": "COMPLETED",
                        }
                    }
                ),
            },
        )

        # 2. Artifact with non-existent syllabus_document_id
        eval_id2 = str(uuid.uuid4())
        slm_id2 = str(uuid.uuid4())
        conn.execute(
            text("INSERT INTO documents (document_id, title) VALUES (:did, :title)"),
            {"did": slm_id2, "title": "Module 2 SLM"},
        )
        conn.execute(
            text(
                "INSERT INTO evaluation_jobs "
                "(evaluation_id, submitted_by, completed_at) "
                "VALUES (:eid, :uid, '2026-08-05 10:00:00')"
            ),
            {"eid": eval_id2, "uid": user_id},
        )
        conn.execute(
            text(insert_results_sql),
            {
                "rid": str(uuid.uuid4()),
                "eid": eval_id2,
                "did": slm_id2,
                "advisory": json.dumps(
                    {
                        "syllabus_alignment": {
                            "syllabus_document_id": unknown_syllabus_id,
                            "status": "MEETS",
                            "processing_state": "COMPLETED",
                        }
                    }
                ),
            },
        )

        # 3. Artifact with invalid UUID format
        eval_id3 = str(uuid.uuid4())
        slm_id3 = str(uuid.uuid4())
        conn.execute(
            text("INSERT INTO documents (document_id, title) VALUES (:did, :title)"),
            {"did": slm_id3, "title": "Module 3 SLM"},
        )
        conn.execute(
            text(
                "INSERT INTO evaluation_jobs "
                "(evaluation_id, submitted_by, completed_at) "
                "VALUES (:eid, :uid, '2026-08-05 10:00:00')"
            ),
            {"eid": eval_id3, "uid": user_id},
        )
        conn.execute(
            text(insert_results_sql),
            {
                "rid": str(uuid.uuid4()),
                "eid": eval_id3,
                "did": slm_id3,
                "advisory": json.dumps(
                    {
                        "syllabus_alignment": {
                            "syllabus_document_id": "not-a-uuid",
                            "status": "MEETS",
                            "processing_state": "COMPLETED",
                        }
                    }
                ),
            },
        )

    _run_upgrade(db_url)

    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT count(*) FROM syllabus_alignment_runs")
        ).scalar()
        assert count == 0


def test_idempotency_and_preservation_of_existing_data(tmp_path):
    """Running upgrade twice does not duplicate rows; existing runs preserved."""
    db_path = tmp_path / f"idempotent-{uuid.uuid4()}.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    engine = create_engine(db_url)
    _setup_test_database(engine)

    user_id = str(uuid.uuid4())
    slm_id = str(uuid.uuid4())
    preexisting_slm_id = str(uuid.uuid4())
    syllabus_id = str(uuid.uuid4())
    eval_id = str(uuid.uuid4())
    preexisting_alignment_id = str(uuid.uuid4())

    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO users (user_id, email) VALUES (:uid, :email)"),
            {"uid": user_id, "email": "faculty@lspu.edu.ph"},
        )
        conn.execute(
            text("INSERT INTO documents (document_id, title) VALUES (:did, :title)"),
            [
                {"did": slm_id, "title": "Module 1 SLM"},
                {"did": preexisting_slm_id, "title": "Module Pre-existing"},
                {"did": syllabus_id, "title": "IT 101 Syllabus"},
            ],
        )
        # Pre-existing alignment row
        conn.execute(
            text(
                "INSERT INTO syllabus_alignment_runs ("
                "alignment_id, slm_document_id, syllabus_document_id, requested_by, "
                "status, alignment_level, justification, created_at, updated_at"
                ") VALUES ("
                ":aid, :slm_id, :syl_id, :uid, 'COMPLETED', 'MEETS', 'Pre-existing', "
                "'2026-08-01 00:00:00', '2026-08-01 00:00:00')"
            ),
            {
                "aid": preexisting_alignment_id,
                "slm_id": preexisting_slm_id,
                "syl_id": syllabus_id,
                "uid": user_id,
            },
        )
        # Advisory outputs for preexisting_slm_id (should NOT overwrite or duplicate)
        insert_results_sql = (
            "INSERT INTO agent_results "
            "(agent_result_id, evaluation_id, document_id, "
            "advisory_outputs, created_at) "
            "VALUES (:rid, :eid, :did, :advisory, :created_at)"
        )
        conn.execute(
            text(
                "INSERT INTO evaluation_jobs "
                "(evaluation_id, submitted_by, completed_at) "
                "VALUES (:eid, :uid, '2026-08-05 10:00:00')"
            ),
            {"eid": eval_id, "uid": user_id},
        )
        conn.execute(
            text(insert_results_sql),
            {
                "rid": str(uuid.uuid4()),
                "eid": eval_id,
                "did": preexisting_slm_id,
                "advisory": json.dumps(
                    {
                        "syllabus_alignment": {
                            "syllabus_document_id": syllabus_id,
                            "status": "PARTIALLY_MEETS",
                            "processing_state": "COMPLETED",
                        }
                    }
                ),
                "created_at": "2026-08-05 09:30:00",
            },
        )
        # Multiple advisory outputs for slm_id (newest should be used without collision)
        conn.execute(
            text(insert_results_sql),
            {
                "rid": str(uuid.uuid4()),
                "eid": eval_id,
                "did": slm_id,
                "advisory": json.dumps(
                    {
                        "syllabus_alignment": {
                            "syllabus_document_id": syllabus_id,
                            "status": "DOES_NOT_MEET",
                            "processing_state": "COMPLETED",
                            "statement": "Old output",
                        }
                    }
                ),
                "created_at": "2026-08-04 09:30:00",
            },
        )
        conn.execute(
            text(insert_results_sql),
            {
                "rid": str(uuid.uuid4()),
                "eid": eval_id,
                "did": slm_id,
                "advisory": json.dumps(
                    {
                        "syllabus_alignment": {
                            "syllabus_document_id": syllabus_id,
                            "status": "MEETS",
                            "processing_state": "COMPLETED",
                            "statement": "Newest output",
                        }
                    }
                ),
                "created_at": "2026-08-06 09:30:00",
            },
        )

    # Run 1
    _run_upgrade(db_url)

    with engine.connect() as conn:
        rows = (
            conn.execute(
                text("SELECT * FROM syllabus_alignment_runs ORDER BY created_at")
            )
            .mappings()
            .all()
        )
        assert len(rows) == 2
        # Pre-existing remains untouched
        norm_pre_id = str(rows[0]["alignment_id"]).replace("-", "")
        assert norm_pre_id == preexisting_alignment_id.replace("-", "")
        assert rows[0]["justification"] == "Pre-existing"

        # Backfilled row is the newest one
        norm_slm = str(rows[1]["slm_document_id"]).replace("-", "")
        assert norm_slm == slm_id.replace("-", "")
        assert rows[1]["alignment_level"] == "MEETS"
        assert rows[1]["justification"] == "Newest output"

    # Run 2: ensure running migration again does not cause integrity error or duplicate
    _run_upgrade(db_url)

    with engine.begin() as conn:
        count = conn.execute(
            text("SELECT count(*) FROM syllabus_alignment_runs")
        ).scalar()
        assert count == 2


def test_deterministic_tie_breaking_for_equal_created_at(tmp_path):
    """When created_at timestamps are identical, deterministic ordering chooses
    the agent_result with higher agent_result_id (agent_result_id DESC)."""
    db_path = tmp_path / f"tie-break-{uuid.uuid4()}.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    engine = create_engine(db_url)
    _setup_test_database(engine)

    user_id = str(uuid.uuid4())
    slm_id = str(uuid.uuid4())
    syllabus_id = str(uuid.uuid4())
    eval_id = str(uuid.uuid4())

    lower_id = "00000000-0000-0000-0000-000000000001"
    higher_id = "00000000-0000-0000-0000-000000000002"
    identical_timestamp = "2026-08-05 12:00:00"

    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO users (user_id, email) VALUES (:uid, :email)"),
            {"uid": user_id, "email": "faculty@lspu.edu.ph"},
        )
        conn.execute(
            text("INSERT INTO documents (document_id, title) VALUES (:did, :title)"),
            [
                {"did": slm_id, "title": "Module Tie SLM"},
                {"did": syllabus_id, "title": "IT 101 Syllabus"},
            ],
        )
        conn.execute(
            text(
                "INSERT INTO evaluation_jobs "
                "(evaluation_id, submitted_by, completed_at) "
                "VALUES (:eid, :uid, '2026-08-05 12:00:00')"
            ),
            {"eid": eval_id, "uid": user_id},
        )

        insert_sql = (
            "INSERT INTO agent_results "
            "(agent_result_id, evaluation_id, document_id, "
            "advisory_outputs, created_at) "
            "VALUES (:rid, :eid, :did, :advisory, :created_at)"
        )
        # Insert lower_id first
        conn.execute(
            text(insert_sql),
            {
                "rid": lower_id,
                "eid": eval_id,
                "did": slm_id,
                "advisory": json.dumps(
                    {
                        "syllabus_alignment": {
                            "syllabus_document_id": syllabus_id,
                            "status": "PARTIALLY_MEETS",
                            "processing_state": "COMPLETED",
                            "statement": "From lower agent_result_id",
                        }
                    }
                ),
                "created_at": identical_timestamp,
            },
        )
        # Insert higher_id second
        conn.execute(
            text(insert_sql),
            {
                "rid": higher_id,
                "eid": eval_id,
                "did": slm_id,
                "advisory": json.dumps(
                    {
                        "syllabus_alignment": {
                            "syllabus_document_id": syllabus_id,
                            "status": "MEETS",
                            "processing_state": "COMPLETED",
                            "statement": "From higher agent_result_id",
                        }
                    }
                ),
                "created_at": identical_timestamp,
            },
        )

    _run_upgrade(db_url)

    with engine.connect() as conn:
        rows = (
            conn.execute(text("SELECT * FROM syllabus_alignment_runs")).mappings().all()
        )
        assert len(rows) == 1
        assert rows[0]["justification"] == "From higher agent_result_id"
        assert rows[0]["alignment_level"] == "MEETS"
