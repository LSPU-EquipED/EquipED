"""change agent_results.subtotal from Integer to Float

Revision ID: 20260523_0013
Revises: 20260522_0012
Create Date: 2026-05-23
"""

from alembic import op
import sqlalchemy as sa


revision = "20260523_0013"
down_revision = "20260522_0012"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("agent_results") as batch_op:
        batch_op.alter_column(
            "subtotal",
            type_=sa.Float(),
            existing_type=sa.Integer(),
            existing_nullable=False,
            existing_server_default=None,
        )


def downgrade():
    with op.batch_alter_table("agent_results") as batch_op:
        batch_op.alter_column(
            "subtotal",
            type_=sa.Integer(),
            existing_type=sa.Float(),
            existing_nullable=False,
            existing_server_default=None,
        )
