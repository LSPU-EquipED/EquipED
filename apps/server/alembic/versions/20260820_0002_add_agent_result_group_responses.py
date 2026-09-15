"""add group_responses to agent_results

Revision ID: 20260820_0002
Revises: 20260820_0001
Create Date: 2026-08-20

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "20260820_0002"
down_revision = "20260820_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    return column in [c["name"] for c in inspect(bind).get_columns(table)]


def upgrade() -> None:
    if _has_column("agent_results", "group_responses"):
        return
    op.add_column(
        "agent_results", sa.Column("group_responses", sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    if not _has_column("agent_results", "group_responses"):
        return
    op.drop_column("agent_results", "group_responses")
