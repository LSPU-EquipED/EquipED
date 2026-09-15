"""Add target_agent column to evaluation_jobs table.

Revision ID: 20260908_0002
Revises: 20260902_0001
Create Date: 2026-09-08 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260908_0002"
down_revision: str | None = "20260902_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "evaluation_jobs",
        sa.Column("target_agent", sa.String(length=32), nullable=True),
    )
    op.execute(
        "UPDATE evaluation_jobs SET target_agent = 'all' WHERE target_agent IS NULL"
    )
    with op.batch_alter_table("evaluation_jobs") as batch_op:
        batch_op.alter_column(
            "target_agent",
            existing_type=sa.String(length=32),
            nullable=False,
        )
    op.create_index(
        "idx_jobs_doc_target_agent",
        "evaluation_jobs",
        ["document_id", "target_agent"],
    )


def downgrade() -> None:
    op.drop_index("idx_jobs_doc_target_agent", table_name="evaluation_jobs")
    op.drop_column("evaluation_jobs", "target_agent")
