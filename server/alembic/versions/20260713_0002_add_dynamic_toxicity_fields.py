"""add dynamic toxicity assessment fields

Revision ID: 20260713_0002
Revises: 20260713_0001
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260713_0002"
down_revision: str | Sequence[str] | None = "20260713_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "model_validations",
        sa.Column("toxicity_score", sa.Numeric(5, 4), nullable=True),
    )
    op.add_column(
        "model_validations",
        sa.Column("toxicity_label", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "model_validations",
        sa.Column("toxicity_explanation", sa.Text(), nullable=True),
    )
    op.add_column(
        "model_validations",
        sa.Column("toxicity_model", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "model_validations",
        sa.Column("toxicity_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "model_validations",
        sa.Column("toxicity_assessed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("model_validations", "toxicity_assessed_at")
    op.drop_column("model_validations", "toxicity_error")
    op.drop_column("model_validations", "toxicity_model")
    op.drop_column("model_validations", "toxicity_explanation")
    op.drop_column("model_validations", "toxicity_label")
    op.drop_column("model_validations", "toxicity_score")
