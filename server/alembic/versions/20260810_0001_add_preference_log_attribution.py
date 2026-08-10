"""add agent_name/criterion_id to preference_logs

Revision ID: 20260810_0001
Revises: 20260808_0002
Create Date: 2026-08-10
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "20260810_0001"
down_revision = "20260808_0002"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    return column in [c["name"] for c in inspect(bind).get_columns(table)]


def upgrade() -> None:
    if not _has_column("preference_logs", "agent_name"):
        op.add_column(
            "preference_logs", sa.Column("agent_name", sa.String(length=32), nullable=True)
        )
    if not _has_column("preference_logs", "criterion_id"):
        op.add_column(
            "preference_logs",
            sa.Column("criterion_id", sa.String(length=100), nullable=True),
        )


def downgrade() -> None:
    if _has_column("preference_logs", "criterion_id"):
        op.drop_column("preference_logs", "criterion_id")
    if _has_column("preference_logs", "agent_name"):
        op.drop_column("preference_logs", "agent_name")
