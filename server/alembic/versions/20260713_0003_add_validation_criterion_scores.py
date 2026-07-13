"""add criterion-level model validation scores

Revision ID: 20260713_0003
Revises: 20260713_0002
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260713_0003"
down_revision: str | Sequence[str] | None = "20260713_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_validation_criterion_scores",
        sa.Column("expected_score_id", sa.Uuid(), nullable=False),
        sa.Column("validation_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.String(length=50), nullable=False),
        sa.Column("criterion_id", sa.String(length=100), nullable=False),
        sa.Column("criterion_title", sa.String(length=300), nullable=False),
        sa.Column("expected_score", sa.Integer(), nullable=False),
        sa.Column("actual_score", sa.Integer(), nullable=True),
        sa.Column("absolute_error", sa.Numeric(3, 2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["validation_id"], ["model_validations.validation_id"]),
        sa.PrimaryKeyConstraint("expected_score_id"),
        sa.UniqueConstraint(
            "validation_id",
            "agent_id",
            "criterion_id",
            name="uq_validation_agent_criterion",
        ),
    )
    op.create_index(
        "idx_validation_criterion_validation",
        "model_validation_criterion_scores",
        ["validation_id"],
    )
    with op.batch_alter_table("model_validations") as batch_op:
        batch_op.drop_column("expected_score")


def downgrade() -> None:
    with op.batch_alter_table("model_validations") as batch_op:
        batch_op.add_column(
            sa.Column(
                "expected_score",
                sa.Numeric(3, 2),
                nullable=False,
                server_default="1.00",
            )
        )
    op.drop_index(
        "idx_validation_criterion_validation",
        table_name="model_validation_criterion_scores",
    )
    op.drop_table("model_validation_criterion_scores")
