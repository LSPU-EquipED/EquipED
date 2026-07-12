"""add provenance JSON column to agent_results

Revision ID: 20260712_0001
Revises: 20260709_0001
Create Date: 2026-07-12

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260712_0001"
down_revision: str | Sequence[str] | None = "20260709_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_results",
        sa.Column("provenance", sa.JSON, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_results", "provenance")
