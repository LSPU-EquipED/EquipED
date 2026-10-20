"""Add separate ITSO v2 assessment parent; legacy AgentResult is untouched.

Revision ID: 20261020_0002
Revises: 20261020_0001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261020_0002"
down_revision = "20261020_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "itso_assessments",
        sa.Column("assessment_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "evaluation_id",
            sa.Uuid(),
            sa.ForeignKey("evaluation_jobs.evaluation_id"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.document_id"),
            nullable=False,
        ),
        sa.Column(
            "owner_id",
            sa.Uuid(),
            sa.ForeignKey("users.user_id"),
            nullable=False,
        ),
        sa.Column(
            "source_snapshot_id",
            sa.Uuid(),
            sa.ForeignKey("document_source_snapshots.snapshot_id"),
            nullable=False,
        ),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("contract_version", sa.String(80), nullable=False),
        sa.Column("manifest_version", sa.Integer(), nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("execution_status", sa.String(16), nullable=False),
        sa.Column(
            "scoring_complete", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("subtotal", sa.Float(), nullable=True),
        sa.Column("failure_code", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "execution_status IN ('PENDING','RUNNING','COMPLETED','FAILED')",
            name="ck_itso_assessment_execution_status",
        ),
        sa.CheckConstraint(
            "(scoring_complete = false AND subtotal IS NULL) OR "
            "(scoring_complete = true AND subtotal IS NOT NULL "
            "AND subtotal BETWEEN 1 AND 4)",
            name="ck_itso_assessment_subtotal",
        ),
        sa.UniqueConstraint(
            "evaluation_id",
            "contract_version",
            name="uq_itso_assessment_evaluation_contract",
        ),
    )
    op.create_index(
        "ix_itso_assessment_owner_document",
        "itso_assessments",
        ["owner_id", "document_id"],
    )


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM itso_assessments")):
        raise RuntimeError(
            "Downgrade refuses to delete ITSO source or assessment history"
        )
    op.drop_index("ix_itso_assessment_owner_document", table_name="itso_assessments")
    op.drop_table("itso_assessments")
