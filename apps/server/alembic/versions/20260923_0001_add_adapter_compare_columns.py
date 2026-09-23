"""Add lora_scale to evaluation_jobs and model_variant/compare_group_id to
model_validations.

Revision ID: 20260923_0001
Revises: 20260918_0003
Create Date: 2026-09-23 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260923_0001"
down_revision: str | None = "20260918_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "evaluation_jobs",
        sa.Column("lora_scale", sa.Float(), nullable=True),
    )
    op.add_column(
        "model_validations",
        sa.Column("model_variant", sa.String(length=10), nullable=True),
    )
    op.add_column(
        "model_validations",
        sa.Column("compare_group_id", sa.Uuid(as_uuid=True), nullable=True),
    )
    op.create_index(
        "idx_model_validations_compare_group_id",
        "model_validations",
        ["compare_group_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_model_validations_compare_group_id", table_name="model_validations"
    )
    op.drop_column("model_validations", "compare_group_id")
    op.drop_column("model_validations", "model_variant")
    op.drop_column("evaluation_jobs", "lora_scale")
