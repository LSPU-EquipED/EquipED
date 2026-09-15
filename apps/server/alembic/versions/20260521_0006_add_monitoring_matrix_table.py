"""add_monitoring_matrix_table

Revision ID: 20260521_0006
Revises: 20260513_0005
Create Date: 2026-05-21

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260521_0006"
down_revision: Union[str, None] = "20260513_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "monitoring_matrix",
        sa.Column("matrix_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("document_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("evaluation_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("faculty_name", sa.String(length=300), nullable=True),
        sa.Column("program", sa.String(length=300), nullable=True),
        sa.Column(
            "evaluation_status",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'SUBMITTED'"),
        ),
        sa.Column("synthesized_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("domain_scores_json", sa.JSON(), nullable=True),
        sa.Column("flag_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "feedback_status",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'NO_FEEDBACK'"),
        ),
        sa.Column("last_updated", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("matrix_id"),
        sa.UniqueConstraint("document_id"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"]),
        sa.ForeignKeyConstraint(["evaluation_id"], ["evaluation_jobs.evaluation_id"]),
    )


def downgrade() -> None:
    op.drop_table("monitoring_matrix")
