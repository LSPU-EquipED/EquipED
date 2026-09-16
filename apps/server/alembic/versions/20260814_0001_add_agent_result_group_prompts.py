"""add group_prompts to agent_results

Revision ID: 20260814_0001
Revises: 20260811_0004
Create Date: 2026-08-14

"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "20260814_0001"
down_revision = "20260811_0004"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    return column in [c["name"] for c in inspect(bind).get_columns(table)]


def upgrade() -> None:
    if _has_column("agent_results", "group_prompts"):
        return
    op.add_column(
        "agent_results", sa.Column("group_prompts", sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    if not _has_column("agent_results", "group_prompts"):
        return
    op.drop_column("agent_results", "group_prompts")
