"""add agent_generations table and preference_logs generation_id

Revision ID: 20260915_0003
Revises: 20260915_0002
Create Date: 2026-09-15

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "20260915_0003"
down_revision = "20260915_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(table: str) -> bool:
    bind = op.get_bind()
    return table in inspect(bind).get_table_names()


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    return column in [c["name"] for c in inspect(bind).get_columns(table)]


def upgrade() -> None:
    if not _has_table("agent_generations"):
        op.create_table(
            "agent_generations",
            sa.Column("generation_id", sa.Uuid(), primary_key=True),
            sa.Column(
                "agent_result_id",
                sa.Uuid(),
                sa.ForeignKey("agent_results.agent_result_id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "form_snapshot_id",
                sa.Uuid(),
                sa.ForeignKey(
                    "evaluation_form_snapshots.snapshot_id", ondelete="SET NULL"
                ),
                nullable=True,
                index=True,
            ),
            sa.Column("evaluation_id", sa.Uuid(), nullable=False, index=True),
            sa.Column("document_id", sa.Uuid(), nullable=False, index=True),
            sa.Column("agent_id", sa.String(32), nullable=False, index=True),
            sa.Column("unit_key", sa.String(64), nullable=False),
            sa.Column("criterion_ids", sa.JSON(), nullable=False),
            sa.Column("prompt_text", sa.Text(), nullable=False),
            sa.Column("prompt_messages", sa.JSON(), nullable=True),
            sa.Column("response_text", sa.Text(), nullable=False),
            sa.Column("response_json", sa.JSON(), nullable=True),
            sa.Column("response_contract_key", sa.String(64), nullable=False),
            sa.Column(
                "response_contract_version",
                sa.Integer(),
                nullable=False,
                server_default="1",
            ),
            sa.Column("model_name", sa.String(128), nullable=False),
            sa.Column("prompt_version_id", sa.Uuid(), nullable=True),
            sa.Column(
                "envelope_status",
                sa.String(32),
                nullable=False,
                server_default="ok",
            ),
            sa.Column("generation_provenance", sa.JSON(), nullable=True),
            sa.Column("prompt_sha256", sa.String(64), nullable=False),
            sa.Column("response_sha256", sa.String(64), nullable=False),
            sa.Column(
                "capture_origin",
                sa.String(32),
                nullable=False,
                server_default="native",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.UniqueConstraint(
                "agent_result_id",
                "unit_key",
                name="uq_agent_generations_result_unit",
            ),
        )

    if not _has_column("preference_logs", "generation_id"):
        with op.batch_alter_table("preference_logs") as batch_op:
            batch_op.add_column(sa.Column("generation_id", sa.Uuid(), nullable=True))
            batch_op.create_foreign_key(
                "fk_preference_logs_generation_id",
                "agent_generations",
                ["generation_id"],
                ["generation_id"],
                ondelete="SET NULL",
            )
            batch_op.create_index(
                "idx_pref_logs_generation_id",
                ["generation_id"],
            )


def downgrade() -> None:
    if _has_column("preference_logs", "generation_id"):
        with op.batch_alter_table("preference_logs") as batch_op:
            batch_op.drop_index("idx_pref_logs_generation_id")
            batch_op.drop_column("generation_id")

    if _has_table("agent_generations"):
        op.drop_table("agent_generations")
