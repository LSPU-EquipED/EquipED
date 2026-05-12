"""add evaluation_jobs table

Revision ID: 20260511_0004
Revises: 20260507_0003
Create Date: 2026-05-11 00:04:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260511_0004"
down_revision = "20260507_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evaluation_jobs",
        sa.Column("evaluation_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("syllabus_id", sa.Uuid(), nullable=False),
        sa.Column("curriculum_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("submitted_by", sa.Uuid(), nullable=True),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"]),
        sa.ForeignKeyConstraint(["syllabus_id"], ["documents.document_id"]),
        sa.ForeignKeyConstraint(["curriculum_id"], ["documents.document_id"]),
        sa.ForeignKeyConstraint(["submitted_by"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("evaluation_id"),
    )

    op.create_index("idx_jobs_document_id", "evaluation_jobs", ["document_id"])
    op.create_index("idx_jobs_status", "evaluation_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("idx_jobs_status", table_name="evaluation_jobs")
    op.drop_index("idx_jobs_document_id", table_name="evaluation_jobs")
    op.drop_table("evaluation_jobs")
