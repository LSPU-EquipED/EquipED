"""add agent advisory outputs (repair migration)

This migration was originally registered under revision id ``20260801_0001``,
colliding with ``20260801_0001_add_confirmed_program_to_evaluation_jobs``
(copy-pasted id from an unmerged branch), which left the alembic graph with a
duplicate revision and multiple heads. It was never applied: databases on the
linear chain already carry the ``agent_results.advisory_outputs`` column.

It is re-registered here as ``20260808_0000`` grafted onto the current chain
tip, with conditional ops so already-migrated databases no-op and fresh
databases still receive the column.

Revision ID: 20260808_0000
Revises: 20260803_0002
Create Date: 2026-08-08
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "20260808_0000"
down_revision = "20260803_0002"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    return column in [c["name"] for c in inspect(bind).get_columns(table)]


def upgrade() -> None:
    if _has_column("agent_results", "advisory_outputs"):
        return
    op.add_column(
        "agent_results", sa.Column("advisory_outputs", sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    if not _has_column("agent_results", "advisory_outputs"):
        return
    op.drop_column("agent_results", "advisory_outputs")
