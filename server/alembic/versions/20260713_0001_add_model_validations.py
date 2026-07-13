"""add model validation benchmark records

Revision ID: 20260713_0001
Revises: 20260712_0001
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260713_0001"
down_revision: str | Sequence[str] | None = "20260712_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_validations",
        sa.Column("validation_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_id", sa.Uuid(), nullable=False),
        sa.Column("expected_score", sa.Numeric(3, 2), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"]),
        sa.ForeignKeyConstraint(
            ["evaluation_id"], ["evaluation_jobs.evaluation_id"]
        ),
        sa.PrimaryKeyConstraint("validation_id"),
        sa.UniqueConstraint(
            "evaluation_id", name="uq_model_validations_evaluation"
        ),
    )
    op.create_index(
        "idx_model_validations_created_by",
        "model_validations",
        ["created_by"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_model_validations_created_by", table_name="model_validations"
    )
    op.drop_table("model_validations")
