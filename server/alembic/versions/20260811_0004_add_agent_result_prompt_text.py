"""add prompt_text to agent_results

Revision ID: 20260811_0004
Revises: 20260811_0003
Create Date: 2026-08-10
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "20260811_0004"
down_revision = "20260811_0003"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    return column in [c["name"] for c in inspect(bind).get_columns(table)]


def upgrade() -> None:
    if _has_column("agent_results", "prompt_text"):
        return
    op.add_column("agent_results", sa.Column("prompt_text", sa.Text(), nullable=True))


def downgrade() -> None:
    if not _has_column("agent_results", "prompt_text"):
        return
    op.drop_column("agent_results", "prompt_text")
