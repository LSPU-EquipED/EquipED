"""Add run-status columns and a status token to dpo_training_jobs.

Revision ID: 20261010_0001
Revises: 20261006_0001
Create Date: 2026-10-10 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261010_0001"
down_revision: str | None = "20261006_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = (
    sa.Column("status_token_hash", sa.String(64), nullable=True),
    sa.Column("status_expires_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("run_stage", sa.String(24), nullable=True),
    sa.Column("run_step", sa.Integer(), nullable=True),
    sa.Column("run_total", sa.Integer(), nullable=True),
    sa.Column("run_message", sa.Text(), nullable=True),
    sa.Column("run_reported_at", sa.DateTime(timezone=True), nullable=True),
)


def upgrade() -> None:
    for column in _COLUMNS:
        op.add_column("dpo_training_jobs", column.copy())


def downgrade() -> None:
    for column in reversed(_COLUMNS):
        op.drop_column("dpo_training_jobs", column.name)
