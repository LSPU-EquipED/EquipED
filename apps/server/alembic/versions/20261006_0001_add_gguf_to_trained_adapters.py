"""Add GGUF metadata columns to trained_adapters.

Revision ID: 20261006_0001
Revises: 20261003_0001
Create Date: 2026-10-06 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261006_0001"
down_revision: str | None = "20261003_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "trained_adapters",
        sa.Column("gguf_storage_key", sa.String(512), nullable=True),
    )
    op.add_column(
        "trained_adapters",
        sa.Column("gguf_sha256", sa.String(64), nullable=True),
    )
    op.add_column(
        "trained_adapters",
        sa.Column("gguf_size_bytes", sa.Integer(), nullable=True),
    )
    op.add_column(
        "trained_adapters",
        sa.Column("gguf_uploaded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "trained_adapters",
        sa.Column("gguf_upload_token_hash", sa.String(64), nullable=True),
    )
    op.add_column(
        "trained_adapters",
        sa.Column("gguf_upload_expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("trained_adapters", "gguf_upload_expires_at")
    op.drop_column("trained_adapters", "gguf_upload_token_hash")
    op.drop_column("trained_adapters", "gguf_uploaded_at")
    op.drop_column("trained_adapters", "gguf_size_bytes")
    op.drop_column("trained_adapters", "gguf_sha256")
    op.drop_column("trained_adapters", "gguf_storage_key")
