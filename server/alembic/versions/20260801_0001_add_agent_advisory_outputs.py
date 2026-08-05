"""add agent advisory outputs

Revision ID: 20260801_0001
Revises: 20260730_0001
Create Date: 2026-08-01
"""

from alembic import op
import sqlalchemy as sa

revision = "20260801_0001"
down_revision = "20260730_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_results", sa.Column("advisory_outputs", sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("agent_results", "advisory_outputs")
