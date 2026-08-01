"""Add confirmed_program column to evaluation_jobs table.

Revision ID: 20260801_0001
Revises: 20260716_0001
Create Date: 2026-08-01 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260801_0001"
down_revision: Union[str, None] = "20260716_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "evaluation_jobs",
        sa.Column("confirmed_program", sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("evaluation_jobs", "confirmed_program")
