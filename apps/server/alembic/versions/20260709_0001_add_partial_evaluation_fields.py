"""add partial_without_curriculum and partial_reason to evaluation_jobs

Revision ID: 20260709_0001
Revises: 20260704_0001
Create Date: 2026-07-09 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260709_0001"
down_revision: Union[str, None] = "20260704_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "evaluation_jobs",
        sa.Column(
            "partial_without_curriculum",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "evaluation_jobs",
        sa.Column("partial_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("evaluation_jobs", "partial_reason")
    op.drop_column("evaluation_jobs", "partial_without_curriculum")
