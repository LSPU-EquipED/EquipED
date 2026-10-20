"""Add immutable ITSO source snapshots and durable preparation ledger.

Revision ID: 20261020_0001
Revises: 20261019_0001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261020_0001"
down_revision = "20261019_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_source_snapshots",
        sa.Column("snapshot_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.document_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "owner_id",
            sa.Uuid(),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("canonical_hash", sa.String(64), nullable=False),
        sa.Column("extractor_version", sa.String(100), nullable=False),
        sa.Column("canonicalization_version", sa.String(100), nullable=False),
        sa.Column("canonical_text", sa.Text(), nullable=False),
        sa.Column("page_map", sa.JSON(), nullable=False),
        sa.Column("reference_inventory", sa.JSON(), nullable=False),
        sa.Column("inventory_hash", sa.String(64), nullable=False),
        sa.Column("inventory_version", sa.String(100), nullable=False),
        sa.Column("inventory_complete", sa.Boolean(), nullable=False),
        sa.Column("inventory_uncertainties", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "document_id",
            "source_hash",
            "extractor_version",
            name="uq_source_snapshot_identity",
        ),
    )
    op.create_index(
        "ix_source_snapshot_document", "document_source_snapshots", ["document_id"]
    )
    op.create_table(
        "document_source_preparations",
        sa.Column("preparation_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.document_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "owner_id",
            sa.Uuid(),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("extractor_version", sa.String(100), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("claim_token", sa.Uuid(), nullable=True),
        sa.Column("failure_code", sa.String(100), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "state IN ('PENDING','RUNNING','READY','FAILED')",
            name="ck_source_preparation_state",
        ),
        sa.CheckConstraint(
            "attempt_count BETWEEN 0 AND 2", name="ck_source_preparation_attempts"
        ),
        sa.UniqueConstraint(
            "document_id",
            "source_hash",
            "extractor_version",
            name="uq_source_preparation_identity",
        ),
    )
    op.create_index(
        "ix_source_preparation_state", "document_source_preparations", ["state"]
    )


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM document_source_snapshots")):
        raise RuntimeError(
            "Downgrade refuses to delete ITSO source or assessment history"
        )
    if op.get_bind().scalar(
        sa.text("SELECT COUNT(*) FROM document_source_preparations")
    ):
        raise RuntimeError(
            "Downgrade refuses to delete ITSO source or assessment history"
        )
    op.drop_index(
        "ix_source_preparation_state", table_name="document_source_preparations"
    )
    op.drop_table("document_source_preparations")
    op.drop_index("ix_source_snapshot_document", table_name="document_source_snapshots")
    op.drop_table("document_source_snapshots")
