"""add dpo_training_jobs and trained_adapters tables

Revision ID: 20260917_0001
Revises: 20260915_0003
Create Date: 2026-09-17

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "20260917_0001"
down_revision = "20260915_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(table: str) -> bool:
    bind = op.get_bind()
    return table in inspect(bind).get_table_names()


def upgrade() -> None:
    if not _has_table("dpo_training_jobs"):
        op.create_table(
            "dpo_training_jobs",
            sa.Column("job_id", sa.Uuid(), primary_key=True),
            sa.Column("agent_id", sa.String(32), nullable=False, index=True),
            sa.Column(
                "status", sa.String(20), nullable=False, server_default="pending"
            ),
            sa.Column(
                "created_by",
                sa.Uuid(),
                sa.ForeignKey("users.user_id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("pairs_content", sa.Text(), nullable=False),
            sa.Column("provenance_content", sa.Text(), nullable=False),
            sa.Column("manifest_json", sa.JSON(), nullable=False),
            sa.Column("download_token_hash", sa.String(64), nullable=False),
            sa.Column(
                "download_expires_at", sa.DateTime(timezone=True), nullable=False
            ),
            sa.Column(
                "download_used_at", sa.DateTime(timezone=True), nullable=True
            ),
            sa.Column("upload_token_hash", sa.String(64), nullable=False),
            sa.Column(
                "upload_expires_at", sa.DateTime(timezone=True), nullable=False
            ),
            sa.Column("upload_used_at", sa.DateTime(timezone=True), nullable=True),
            sa.CheckConstraint(
                "status IN ('pending', 'downloaded', 'completed')",
                name="ck_dpo_training_jobs_status",
            ),
        )
        op.create_index(
            "idx_dpo_training_jobs_created_at",
            "dpo_training_jobs",
            [sa.text("created_at DESC")],
        )

    if not _has_table("trained_adapters"):
        op.create_table(
            "trained_adapters",
            sa.Column("adapter_id", sa.Uuid(), primary_key=True),
            sa.Column("agent_id", sa.String(32), nullable=False, index=True),
            sa.Column(
                "job_id",
                sa.Uuid(),
                sa.ForeignKey("dpo_training_jobs.job_id", ondelete="RESTRICT"),
                nullable=False,
                index=True,
            ),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("file_path", sa.String(512), nullable=False),
            sa.Column("file_sha256", sa.String(64), nullable=False),
            sa.Column("size_bytes", sa.Integer(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )


def downgrade() -> None:
    if _has_table("trained_adapters"):
        op.drop_table("trained_adapters")
    if _has_table("dpo_training_jobs"):
        op.drop_table("dpo_training_jobs")
