"""Add agent_adapter_publication and adapter selection columns.

Revision ID: 20260929_0001
Revises: 20260923_0001
Create Date: 2026-09-29 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260929_0001"
down_revision: str | None = "20260923_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_adapter_publication",
        sa.Column("agent_id", sa.String(length=32), primary_key=True),
        sa.Column(
            "adapter_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("trained_adapters.adapter_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "published_by",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.user_id"),
            nullable=False,
        ),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column(
        "evaluation_jobs", sa.Column("adapter_request", sa.JSON(), nullable=True)
    )
    op.add_column(
        "evaluation_jobs", sa.Column("adapter_resolution", sa.JSON(), nullable=True)
    )
    with op.batch_alter_table("model_validations") as batch:
        batch.add_column(
            sa.Column(
                "adapter_id",
                sa.Uuid(as_uuid=True),
                sa.ForeignKey(
                    "trained_adapters.adapter_id",
                    name="fk_model_validations_adapter_id",
                    ondelete="RESTRICT",
                ),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("model_validations") as batch:
        batch.drop_column("adapter_id")
    op.drop_column("evaluation_jobs", "adapter_resolution")
    op.drop_column("evaluation_jobs", "adapter_request")
    op.drop_table("agent_adapter_publication")
