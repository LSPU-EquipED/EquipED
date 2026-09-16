"""add academic_year and course_code columns to documents table

Revision ID: 20260704_0001
Revises: 20260701_0002
Create Date: 2026-07-04 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260704_0001"
down_revision: Union[str, None] = "20260701_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("academic_year", sa.String(length=50), nullable=True))
    op.add_column("documents", sa.Column("course_code", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "course_code")
    op.drop_column("documents", "academic_year")
