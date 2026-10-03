"""Add training_summary to trained_adapters.

Revision ID: 20261003_0001
Revises: 20260929_0001
Create Date: 2026-10-03 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261003_0001"
down_revision: str | None = "20260929_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "trained_adapters",
        sa.Column("training_summary", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("trained_adapters", "training_summary")
