"""add item_id and ITEM_REJECT/ITEM_ACCEPT to preference_logs

Revision ID: 20260915_0002
Revises: 20260915_0001
Create Date: 2026-09-15

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "20260915_0002"
down_revision = "20260915_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_ACTIONS = "action IN ('ACCEPT', 'REJECT', 'EDIT')"
_NEW_ACTIONS = (
    "action IN ('ACCEPT', 'REJECT', 'EDIT', 'ITEM_REJECT', 'ITEM_ACCEPT')"
)


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    return column in [c["name"] for c in inspect(bind).get_columns(table)]


def upgrade() -> None:
    if not _has_column("preference_logs", "item_id"):
        with op.batch_alter_table("preference_logs") as batch_op:
            batch_op.add_column(
                sa.Column("item_id", sa.String(length=100), nullable=True)
            )

    with op.batch_alter_table("preference_logs") as batch_op:
        batch_op.drop_constraint("ck_preference_logs_action", type_="check")
        batch_op.create_check_constraint("ck_preference_logs_action", _NEW_ACTIONS)


def downgrade() -> None:
    with op.batch_alter_table("preference_logs") as batch_op:
        batch_op.drop_constraint("ck_preference_logs_action", type_="check")
        batch_op.create_check_constraint("ck_preference_logs_action", _OLD_ACTIONS)

    if _has_column("preference_logs", "item_id"):
        with op.batch_alter_table("preference_logs") as batch_op:
            batch_op.drop_column("item_id")
