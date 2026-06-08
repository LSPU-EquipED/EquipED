"""add execution ownership fields to evaluation_jobs

Revision ID: 20260607_0015
Revises: 20260527_0014
Create Date: 2026-06-07
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260607_0015"
down_revision = "20260527_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "evaluation_jobs",
        sa.Column("execution_token", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "evaluation_jobs",
        sa.Column(
            "execution_started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "evaluation_jobs",
        sa.Column(
            "execution_heartbeat_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("evaluation_jobs", "execution_heartbeat_at")
    op.drop_column("evaluation_jobs", "execution_started_at")
    op.drop_column("evaluation_jobs", "execution_token")
