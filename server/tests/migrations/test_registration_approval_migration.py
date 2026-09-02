"""Focused SQLite migration tests for registration approval (20260830_0002).

Covers:
- Linear migration lineage: 20260829_0006 -> 20260830_0001 -> 20260830_0002.
- Clean SQLite upgrade from 20260830_0001 to 20260830_0002 via batch_alter_table.
- Users table column additions: faculty_id, department, program, account_status,
  approved_at, reviewed_at, reviewed_by, and reviewer self-referential FK.
- Creation of pending_registrations table with all constraints and FKs.
- Reversible downgrade of 20260830_0002 back to 20260830_0001.
- Preservation of downgrade refusal on 20260830_0001 (irreversible policy).
- Re-upgrade replay cleanly.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest
from alembic.command import downgrade as alembic_downgrade
from alembic.command import upgrade as alembic_upgrade
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

PREV_REV = "20260829_0006"
EMAIL_REV = "20260830_0001"
APPROVAL_REV = "20260830_0002"

USERS_NEW_COLS = {
    "faculty_id",
    "department",
    "program",
    "account_status",
    "approved_at",
    "reviewed_at",
    "reviewed_by",
}

PENDING_REG_COLS = {
    "registration_id",
    "existing_user_id",
    "token_hash",
    "name",
    "email",
    "password_hash",
    "faculty_id",
    "department",
    "program",
    "otp_hash",
    "otp_expires_at",
    "otp_attempts",
    "last_sent_at",
    "created_at",
}


def _cfg(db_url: str) -> Config:
    ini = str(REPO_ROOT / "server" / "alembic.ini")
    c = Config(ini)
    c.set_main_option("sqlalchemy.url", db_url.replace("%", "%%"))
    return c


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


def _current(engine) -> str | None:
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        return ctx.get_current_revision()


def _stamp(engine, revision: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS alembic_version "
                "(version_num VARCHAR(32) PRIMARY KEY)"
            )
        )
        conn.execute(text("DELETE FROM alembic_version"))
        conn.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:rev)"),
            {"rev": revision},
        )


def _setup_base_tables(engine) -> None:
    """Create the users and sessions tables as they exist at 20260830_0001."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE users ("
                "  user_id VARCHAR(36) PRIMARY KEY,"
                "  name VARCHAR(300) NOT NULL,"
                "  email VARCHAR(300) NOT NULL UNIQUE,"
                "  role VARCHAR(50) NOT NULL,"
                "  password_hash VARCHAR(512) NOT NULL,"
                "  is_active BOOLEAN NOT NULL DEFAULT 1,"
                "  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,"
                "  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE sessions ("
                "  session_id VARCHAR(36) PRIMARY KEY,"
                "  user_id VARCHAR(36) NOT NULL,"
                "  token_hash VARCHAR(128) NOT NULL UNIQUE,"
                "  expires_at DATETIME NOT NULL,"
                "  revoked_at DATETIME NULL,"
                "  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,"
                "  FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE"
                ")"
            )
        )


def test_lineage_chain_and_single_head():
    """Verify 20260829_0006 -> 20260830_0001 -> 20260830_0002 lineage."""
    script = ScriptDirectory.from_config(_cfg("sqlite+pysqlite:///:memory:"))

    rev_0001 = script.get_revision(EMAIL_REV)
    assert rev_0001 is not None
    assert rev_0001.down_revision == PREV_REV

    rev_0002 = script.get_revision(APPROVAL_REV)
    assert rev_0002 is not None
    assert rev_0002.down_revision == EMAIL_REV

    assert script.get_heads() == ["20260902_0001"]


def test_upgrade_and_downgrade_on_sqlite(tmp_path: Path):
    """Test upgrade, schema checks, row insertions, and downgrade cycle."""
    db_path = tmp_path / "registration_approval.db"
    db_url = f"sqlite+pysqlite:///{db_path}"
    engine = create_engine(db_url)

    _setup_base_tables(engine)
    _stamp(engine, EMAIL_REV)

    # Upgrade to 20260830_0002
    _run(alembic_upgrade, _cfg(db_url), APPROVAL_REV)
    assert _current(engine) == APPROVAL_REV

    inspector = inspect(engine)

    # 1. Verify users table columns
    user_cols = {c["name"]: c for c in inspector.get_columns("users")}
    for col in USERS_NEW_COLS:
        assert col in user_cols

    assert user_cols["account_status"]["nullable"] is False
    assert user_cols["faculty_id"]["nullable"] is True
    assert user_cols["department"]["nullable"] is True
    assert user_cols["program"]["nullable"] is True
    assert user_cols["approved_at"]["nullable"] is True
    assert user_cols["reviewed_at"]["nullable"] is True
    assert user_cols["reviewed_by"]["nullable"] is True

    # 2. Verify pending_registrations table
    assert "pending_registrations" in set(inspector.get_table_names())
    pending_cols = {c["name"] for c in inspector.get_columns("pending_registrations")}
    assert pending_cols == PENDING_REG_COLS

    pending_uniq = {
        uc["name"] for uc in inspector.get_unique_constraints("pending_registrations")
    }
    assert "uq_pending_registrations_token_hash" in pending_uniq
    assert "uq_pending_registrations_email" in pending_uniq

    pending_fks = inspector.get_foreign_keys("pending_registrations")
    assert any(
        fk["referred_table"] == "users"
        and fk["referred_columns"] == ["user_id"]
        and fk["constrained_columns"] == ["existing_user_id"]
        for fk in pending_fks
    )

    # 3. Verify data insertion with reviewer FK and pending registrations
    admin_id = str(uuid.uuid4())
    faculty_id = str(uuid.uuid4())
    reg_id = str(uuid.uuid4())

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users ("
                "  user_id, name, email, role, password_hash, account_status"
                ") VALUES ("
                "  :id, 'Admin', 'admin@lspu.edu.ph', 'admin', 'h1', 'approved'"
                ")"
            ),
            {"id": admin_id},
        )
        conn.execute(
            text(
                "INSERT INTO users ("
                "  user_id, name, email, role, password_hash, account_status,"
                "  reviewed_by, faculty_id, department, program"
                ") VALUES ("
                "  :id, 'Faculty', 'fac@lspu.edu.ph', 'faculty', 'h2', 'approved',"
                "  :admin_id, 'FAC-001', 'CCS', 'BSIT'"
                ")"
            ),
            {"id": faculty_id, "admin_id": admin_id},
        )
        conn.execute(
            text(
                "INSERT INTO pending_registrations ("
                "  registration_id, existing_user_id, token_hash, name, email,"
                "  password_hash, faculty_id, department, program, otp_hash,"
                "  otp_expires_at, otp_attempts, last_sent_at"
                ") VALUES ("
                "  :reg_id, :existing_user_id, 'token_h', 'Applicant',"
                "  'app@lspu.edu.ph', 'h3', 'FAC-002', 'CCS', 'BSCS', 'otp_h',"
                "  datetime('now', '+1 hour'), 0, datetime('now')"
                ")"
            ),
            {"reg_id": reg_id, "existing_user_id": faculty_id},
        )

    with engine.connect() as conn:
        user_row = (
            conn.execute(
                text(
                    "SELECT account_status, reviewed_by, faculty_id "
                    "FROM users WHERE user_id = :id"
                ),
                {"id": faculty_id},
            )
            .mappings()
            .one()
        )
        assert user_row["account_status"] == "approved"
        assert user_row["reviewed_by"] == admin_id
        assert user_row["faculty_id"] == "FAC-001"

        reg_row = (
            conn.execute(
                text(
                    "SELECT name, email, existing_user_id "
                    "FROM pending_registrations WHERE registration_id = :id"
                ),
                {"id": reg_id},
            )
            .mappings()
            .one()
        )
        assert reg_row["name"] == "Applicant"
        assert reg_row["existing_user_id"] == faculty_id

    # 4. Test downgrade back to 20260830_0001
    _run(alembic_downgrade, _cfg(db_url), EMAIL_REV)
    assert _current(engine) == EMAIL_REV

    inspector_after_down = inspect(engine)
    assert "pending_registrations" not in set(inspector_after_down.get_table_names())
    user_cols_after = {c["name"] for c in inspector_after_down.get_columns("users")}
    for col in USERS_NEW_COLS:
        assert col not in user_cols_after

    # 5. Verify downgrade refusal on 20260830_0001 is preserved
    with pytest.raises(RuntimeError, match="intentionally irreversible"):
        _run(alembic_downgrade, _cfg(db_url), PREV_REV)

    # 6. Re-upgrade replay
    _run(alembic_upgrade, _cfg(db_url), APPROVAL_REV)
    assert _current(engine) == APPROVAL_REV
    inspector_replayed = inspect(engine)
    assert "pending_registrations" in set(inspector_replayed.get_table_names())
    user_cols_replayed = {c["name"] for c in inspector_replayed.get_columns("users")}
    for col in USERS_NEW_COLS:
        assert col in user_cols_replayed

    engine.dispose()
