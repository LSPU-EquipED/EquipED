"""add envelope_status to agent_results

Revision ID: 20260915_0001
Revises: 20260911_0001
Create Date: 2026-09-15

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "20260915_0001"
down_revision = "20260911_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    return column in [c["name"] for c in inspect(bind).get_columns(table)]


def upgrade() -> None:
    if _has_column("agent_results", "envelope_status"):
        return
    op.add_column(
        "agent_results", sa.Column("envelope_status", sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    if not _has_column("agent_results", "envelope_status"):
        return
    op.drop_column("agent_results", "envelope_status")
