"""Tests for pre-snapshot legacy marker migration and model parity."""

from __future__ import annotations

import importlib
import uuid

import pytest
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from sqlalchemy import create_engine, text

BASE_REVISION = "20260829_0005"
TARGET_REVISION = "20260829_0006"
MIG_MODULE = "server.alembic.versions.20260829_0006_add_pre_snapshot_legacy_marker"


def _get_mig():
    return importlib.import_module(MIG_MODULE)


def _run_upgrade(engine):
    mig = _get_mig()
    with engine.begin() as conn:
        context = MigrationContext.configure(conn)
        with Operations.context(context):
            mig.upgrade()


def _run_downgrade(engine):
    mig = _get_mig()
    with engine.begin() as conn:
        context = MigrationContext.configure(conn)
        with Operations.context(context):
            mig.downgrade()


def _create_migration_test_db(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'legacy_marker_test.db'}")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE evaluation_jobs ("
                "evaluation_id TEXT PRIMARY KEY, "
                "document_id TEXT NOT NULL, "
                "status TEXT NOT NULL, "
                "submitted_at DATETIME NOT NULL)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE agent_results ("
                "agent_result_id TEXT PRIMARY KEY, "
                "evaluation_id TEXT NOT NULL, "
                "agent_name TEXT NOT NULL, "
                "form_snapshot_id TEXT NULL)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE evaluation_form_snapshots ("
                "snapshot_id TEXT PRIMARY KEY, "
                "evaluation_id TEXT NOT NULL, "
                "agent_id TEXT NOT NULL)"
            )
        )
        conn.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)")
        )
        conn.execute(
            text("INSERT INTO alembic_version VALUES (:r)"), {"r": BASE_REVISION}
        )
    return engine


def test_migration_metadata():
    mig = _get_mig()
    assert mig.revision == TARGET_REVISION
    assert mig.down_revision == BASE_REVISION


def test_migration_positive_and_negative_backfill_matrix(tmp_path):
    engine = _create_migration_test_db(tmp_path)

    eval_completed_coherent = str(uuid.uuid4())
    eval_failed_coherent = str(uuid.uuid4())
    eval_nonterminal_submitted = str(uuid.uuid4())
    eval_nonterminal_evaluating = str(uuid.uuid4())
    eval_no_results = str(uuid.uuid4())
    eval_with_snapshots = str(uuid.uuid4())
    eval_mixed_bindings = str(uuid.uuid4())
    eval_all_bound_results = str(uuid.uuid4())

    doc_id = str(uuid.uuid4())

    with engine.begin() as conn:
        # 1. Terminal COMPLETED coherent job (>=1 result, 0 snapshots, all NULL)
        # -> MUST BACKFILL TRUE
        conn.execute(
            text(
                "INSERT INTO evaluation_jobs "
                "(evaluation_id, document_id, status, submitted_at) "
                "VALUES (:id, :doc, 'COMPLETED', '2026-01-01')"
            ),
            {"id": eval_completed_coherent, "doc": doc_id},
        )
        conn.execute(
            text("INSERT INTO agent_results VALUES (:rid, :eid, 'sme', NULL)"),
            {"rid": str(uuid.uuid4()), "eid": eval_completed_coherent},
        )
        conn.execute(
            text("INSERT INTO agent_results VALUES (:rid, :eid, 'gad', NULL)"),
            {"rid": str(uuid.uuid4()), "eid": eval_completed_coherent},
        )

        # 2. Terminal FAILED coherent job (>=1 result, 0 snapshots, all NULL)
        # -> MUST BACKFILL TRUE
        conn.execute(
            text(
                "INSERT INTO evaluation_jobs "
                "(evaluation_id, document_id, status, submitted_at) "
                "VALUES (:id, :doc, 'FAILED', '2026-01-01')"
            ),
            {"id": eval_failed_coherent, "doc": doc_id},
        )
        conn.execute(
            text("INSERT INTO agent_results VALUES (:rid, :eid, 'sme', NULL)"),
            {"rid": str(uuid.uuid4()), "eid": eval_failed_coherent},
        )

        # 3. Nonterminal SUBMITTED job -> MUST REMAIN FALSE
        conn.execute(
            text(
                "INSERT INTO evaluation_jobs "
                "(evaluation_id, document_id, status, submitted_at) "
                "VALUES (:id, :doc, 'SUBMITTED', '2026-01-01')"
            ),
            {"id": eval_nonterminal_submitted, "doc": doc_id},
        )
        conn.execute(
            text("INSERT INTO agent_results VALUES (:rid, :eid, 'sme', NULL)"),
            {"rid": str(uuid.uuid4()), "eid": eval_nonterminal_submitted},
        )

        # 4. Nonterminal EVALUATING job -> MUST REMAIN FALSE
        conn.execute(
            text(
                "INSERT INTO evaluation_jobs "
                "(evaluation_id, document_id, status, submitted_at) "
                "VALUES (:id, :doc, 'EVALUATING', '2026-01-01')"
            ),
            {"id": eval_nonterminal_evaluating, "doc": doc_id},
        )
        conn.execute(
            text("INSERT INTO agent_results VALUES (:rid, :eid, 'sme', NULL)"),
            {"rid": str(uuid.uuid4()), "eid": eval_nonterminal_evaluating},
        )

        # 5. Terminal COMPLETED job with zero agent results -> MUST REMAIN FALSE
        conn.execute(
            text(
                "INSERT INTO evaluation_jobs "
                "(evaluation_id, document_id, status, submitted_at) "
                "VALUES (:id, :doc, 'COMPLETED', '2026-01-01')"
            ),
            {"id": eval_no_results, "doc": doc_id},
        )

        # 6. Terminal COMPLETED job with evaluation_form_snapshots -> MUST REMAIN FALSE
        conn.execute(
            text(
                "INSERT INTO evaluation_jobs "
                "(evaluation_id, document_id, status, submitted_at) "
                "VALUES (:id, :doc, 'COMPLETED', '2026-01-01')"
            ),
            {"id": eval_with_snapshots, "doc": doc_id},
        )
        conn.execute(
            text("INSERT INTO agent_results VALUES (:rid, :eid, 'sme', NULL)"),
            {"rid": str(uuid.uuid4()), "eid": eval_with_snapshots},
        )
        conn.execute(
            text("INSERT INTO evaluation_form_snapshots VALUES (:sid, :eid, 'sme')"),
            {"sid": str(uuid.uuid4()), "eid": eval_with_snapshots},
        )

        # 7. Terminal COMPLETED job with mixed bindings -> MUST REMAIN FALSE
        snap_id = str(uuid.uuid4())
        conn.execute(
            text(
                "INSERT INTO evaluation_jobs "
                "(evaluation_id, document_id, status, submitted_at) "
                "VALUES (:id, :doc, 'COMPLETED', '2026-01-01')"
            ),
            {"id": eval_mixed_bindings, "doc": doc_id},
        )
        conn.execute(
            text("INSERT INTO agent_results VALUES (:rid, :eid, 'sme', NULL)"),
            {"rid": str(uuid.uuid4()), "eid": eval_mixed_bindings},
        )
        conn.execute(
            text("INSERT INTO agent_results VALUES (:rid, :eid, 'gad', :snap)"),
            {"rid": str(uuid.uuid4()), "eid": eval_mixed_bindings, "snap": snap_id},
        )

        # 8. Terminal COMPLETED job where all results have non-NULL form_snapshot_id
        # -> MUST REMAIN FALSE
        conn.execute(
            text(
                "INSERT INTO evaluation_jobs "
                "(evaluation_id, document_id, status, submitted_at) "
                "VALUES (:id, :doc, 'COMPLETED', '2026-01-01')"
            ),
            {"id": eval_all_bound_results, "doc": doc_id},
        )
        conn.execute(
            text("INSERT INTO agent_results VALUES (:rid, :eid, 'sme', :snap)"),
            {"rid": str(uuid.uuid4()), "eid": eval_all_bound_results, "snap": snap_id},
        )

    _run_upgrade(engine)

    with engine.connect() as conn:
        rows = (
            conn.execute(
                text(
                    "SELECT evaluation_id, is_pre_snapshot_legacy FROM evaluation_jobs"
                )
            )
            .mappings()
            .all()
        )
        legacy_by_id = {
            r["evaluation_id"]: bool(r["is_pre_snapshot_legacy"]) for r in rows
        }

    assert legacy_by_id[eval_completed_coherent] is True
    assert legacy_by_id[eval_failed_coherent] is True
    assert legacy_by_id[eval_nonterminal_submitted] is False
    assert legacy_by_id[eval_nonterminal_evaluating] is False
    assert legacy_by_id[eval_no_results] is False
    assert legacy_by_id[eval_with_snapshots] is False
    assert legacy_by_id[eval_mixed_bindings] is False
    assert legacy_by_id[eval_all_bound_results] is False

    engine.dispose()


def test_downgrade_unconditionally_refuses():
    mig = _get_mig()
    with pytest.raises(
        RuntimeError, match="Downgrade is not supported for legacy snapshot marker"
    ):
        mig.downgrade()


def test_evaluation_job_model_default_parity(db_session):
    doc_id = uuid.uuid4()
    job = EvaluationJob(
        document_id=doc_id,
        status=EvaluationStatus.SUBMITTED.value,
    )
    db_session.add(job)
    db_session.flush()

    assert job.is_pre_snapshot_legacy is False
