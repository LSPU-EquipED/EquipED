"""harden_admin_models

Revision ID: 20260522_0010
Revises: 20260522_0009
Create Date: 2026-05-22
"""

from __future__ import annotations

import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260522_0010"
down_revision: Union[str, None] = "20260522_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        _rebuild_prompt_versions_to_varchar(bind)
    else:
        with op.batch_alter_table("prompt_versions") as batch_op:
            batch_op.alter_column(
                "prompt_text",
                type_=sa.String(10000),
                existing_type=sa.Text(),
                nullable=False,
            )
    op.execute(sa.text("DROP TABLE IF EXISTS _alembic_tmp_preference_logs"))
    with op.batch_alter_table("preference_logs") as batch_op:
        batch_op.create_check_constraint(
            "ck_preference_logs_action",
            "action IN ('ACCEPT', 'REJECT', 'EDIT')",
        )
    op.create_index("idx_pref_logs_action", "preference_logs", ["action"])
    op.create_index("idx_pref_logs_created_at", "preference_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_pref_logs_created_at", table_name="preference_logs", if_exists=True)
    op.drop_index("idx_pref_logs_action", table_name="preference_logs", if_exists=True)
    op.execute(sa.text("DROP TABLE IF EXISTS _alembic_tmp_preference_logs"))
    with op.batch_alter_table("preference_logs") as batch_op:
        batch_op.drop_constraint("ck_preference_logs_action", type_="check")
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        _rebuild_prompt_versions_to_text(bind)
    else:
        with op.batch_alter_table("prompt_versions") as batch_op:
            batch_op.alter_column(
                "prompt_text",
                type_=sa.Text(),
                existing_type=sa.String(10000),
                nullable=False,
            )


def _rebuild_prompt_versions_to_varchar(bind) -> None:
    """SQLite-safe prompt_text Text→VARCHAR via manual table rebuild."""
    (existing,) = bind.execute(
        sa.text("SELECT sql FROM sqlite_master WHERE type='table' AND name='prompt_versions'")
    ).fetchone()
    new_sql = existing.replace("prompt_text TEXT NOT NULL", "prompt_text VARCHAR(10000) NOT NULL")
    bind.execute(sa.text("DROP TABLE IF EXISTS _alembic_tmp_prompt_versions"))
    bind.execute(sa.text(re.sub(r'CREATE TABLE\s+(?:IF NOT EXISTS\s+)?"?prompt_versions"?', "CREATE TABLE _alembic_tmp_prompt_versions", new_sql, count=1)))
    bind.execute(sa.text("INSERT INTO _alembic_tmp_prompt_versions SELECT * FROM prompt_versions"))
    bind.execute(sa.text("DROP TABLE prompt_versions"))
    bind.execute(sa.text("ALTER TABLE _alembic_tmp_prompt_versions RENAME TO prompt_versions"))


def _rebuild_prompt_versions_to_text(bind) -> None:
    """SQLite-safe prompt_text VARCHAR→TEXT via manual table rebuild."""
    (existing,) = bind.execute(
        sa.text("SELECT sql FROM sqlite_master WHERE type='table' AND name='prompt_versions'")
    ).fetchone()
    new_sql = existing.replace("prompt_text VARCHAR(10000) NOT NULL", "prompt_text TEXT NOT NULL")
    bind.execute(sa.text("DROP TABLE IF EXISTS _alembic_tmp_prompt_versions"))
    bind.execute(sa.text(re.sub(r'CREATE TABLE\s+(?:IF NOT EXISTS\s+)?"?prompt_versions"?', "CREATE TABLE _alembic_tmp_prompt_versions", new_sql, count=1)))
    bind.execute(sa.text("INSERT INTO _alembic_tmp_prompt_versions SELECT * FROM prompt_versions"))
    bind.execute(sa.text("DROP TABLE prompt_versions"))
    bind.execute(sa.text("ALTER TABLE _alembic_tmp_prompt_versions RENAME TO prompt_versions"))
