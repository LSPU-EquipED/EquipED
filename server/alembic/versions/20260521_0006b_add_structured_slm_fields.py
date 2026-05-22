"""add structured SLM fields

Revision ID: 20260521_0006b
Revises: 20260521_0006
Create Date: 2026-05-21 00:06:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260521_0006b"
down_revision = "20260521_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("structured_summary", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("structured_outline", sa.JSON(), nullable=True))
    op.add_column("documents", sa.Column("section_summaries", sa.JSON(), nullable=True))
    op.add_column("documents", sa.Column("key_facts", sa.JSON(), nullable=True))
    op.add_column("documents", sa.Column("processing_warnings", sa.JSON(), nullable=True))
    op.add_column(
        "documents",
        sa.Column(
            "evaluation_readiness",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'PENDING'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("documents", "evaluation_readiness")
    op.drop_column("documents", "processing_warnings")
    op.drop_column("documents", "key_facts")
    op.drop_column("documents", "section_summaries")
    op.drop_column("documents", "structured_outline")
    op.drop_column("documents", "structured_summary")
