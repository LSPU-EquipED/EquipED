"""Add legacy marker to evaluation_jobs and backfill historical evaluations.

Revision ID: 20260829_0006
Revises: 20260829_0005
Create Date: 2026-08-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260829_0006"
down_revision: str | None = "20260829_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add column is_pre_snapshot_legacy to evaluation_jobs
    op.add_column(
        "evaluation_jobs",
        sa.Column(
            "is_pre_snapshot_legacy",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    # 2. Backfill is_pre_snapshot_legacy = TRUE only for coherent terminal jobs:
    # - status in ('COMPLETED', 'FAILED')
    # - has >= 1 AgentResult row
    # - has 0 EvaluationFormSnapshot rows
    # - every AgentResult row has form_snapshot_id IS NULL
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE evaluation_jobs
            SET is_pre_snapshot_legacy = :is_legacy
            WHERE status IN ('COMPLETED', 'FAILED')
              AND EXISTS (
                  SELECT 1 FROM agent_results ar
                  WHERE ar.evaluation_id = evaluation_jobs.evaluation_id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM evaluation_form_snapshots efs
                  WHERE efs.evaluation_id = evaluation_jobs.evaluation_id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM agent_results ar_nonnull
                  WHERE ar_nonnull.evaluation_id = evaluation_jobs.evaluation_id
                    AND ar_nonnull.form_snapshot_id IS NOT NULL
              )
            """
        ).bindparams(sa.bindparam("is_legacy", type_=sa.Boolean)),
        {"is_legacy": True},
    )


def downgrade() -> None:
    raise RuntimeError(
        "Downgrade is not supported for legacy snapshot marker migration "
        "under irreversible migration policy"
    )
