"""Characterize the evaluation admission migration on SQLite."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.command import downgrade, upgrade
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BASE, HEAD = "20260810_0002", "20260811_0001"


def _config(url: str) -> Config:
    config = Config(str(ROOT / "server" / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    return config


def _run(command, config, revision):
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


def test_admission_constraints_upgrade_and_downgrade(tmp_path):
    url = f"sqlite+pysqlite:///{tmp_path / 'admission.db'}"
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE evaluation_jobs (evaluation_id TEXT PRIMARY KEY, "
                "status TEXT NOT NULL, submitted_at TEXT NOT NULL)"
            )
        )
        conn.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)")
        )
        conn.execute(text("INSERT INTO alembic_version VALUES (:rev)"), {"rev": BASE})
    _run(upgrade, _config(url), HEAD)
    inspector = inspect(engine)
    assert {c["name"] for c in inspector.get_columns("evaluation_jobs")} >= {
        "admission_slot"
    }
    assert {
        c["name"]
        for c in inspector.get_columns("evaluation_jobs")
        if c["name"] == "admission_slot" and c["nullable"]
    } == {"admission_slot"}
    assert {c["name"] for c in inspector.get_check_constraints("evaluation_jobs")} >= {
        "ck_evaluation_admission_slot"
    }
    assert {c["name"] for c in inspector.get_unique_constraints("evaluation_jobs")} >= {
        "uq_evaluation_admission_slot"
    }
    indexes = {
        i["name"]: i["column_names"] for i in inspector.get_indexes("evaluation_jobs")
    }
    assert indexes["idx_jobs_admission_fifo"] == [
        "status",
        "submitted_at",
        "evaluation_id",
    ]
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO evaluation_jobs VALUES (:id, 'SUBMITTED', '1', NULL)"),
            {"id": str(uuid4())},
        )
        conn.execute(
            text("INSERT INTO evaluation_jobs VALUES (:id, 'SUBMITTED', '2', NULL)"),
            {"id": str(uuid4())},
        )
        conn.execute(
            text("INSERT INTO evaluation_jobs VALUES (:id, 'SUBMITTED', '3', 1)"),
            {"id": str(uuid4())},
        )
        with pytest.raises(IntegrityError):
            conn.execute(
                text("INSERT INTO evaluation_jobs VALUES (:id, 'SUBMITTED', '4', 1)"),
                {"id": str(uuid4())},
            )
        with pytest.raises(IntegrityError):
            conn.execute(
                text("INSERT INTO evaluation_jobs VALUES (:id, 'SUBMITTED', '5', 2)"),
                {"id": str(uuid4())},
            )
    _run(downgrade, _config(url), BASE)
    inspector = inspect(engine)
    assert "admission_slot" not in {
        c["name"] for c in inspector.get_columns("evaluation_jobs")
    }
    assert not {
        c["name"] for c in inspector.get_check_constraints("evaluation_jobs")
    } & {"ck_evaluation_admission_slot"}
    assert not {
        c["name"] for c in inspector.get_unique_constraints("evaluation_jobs")
    } & {"uq_evaluation_admission_slot"}
    assert "idx_jobs_admission_fifo" not in {
        i["name"] for i in inspector.get_indexes("evaluation_jobs")
    }
    with engine.connect() as conn:
        assert MigrationContext.configure(conn).get_current_revision() == BASE
    engine.dispose()
