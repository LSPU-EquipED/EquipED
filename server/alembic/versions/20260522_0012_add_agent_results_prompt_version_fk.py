"""add prompt_version_id to agent_results

Revision ID: 20260522_0012
Revises: 20260522_0011
Create Date: 2026-05-22
"""

from alembic import op
import sqlalchemy as sa


revision = "20260522_0012"
down_revision = "20260522_0011"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("agent_results") as batch_op:
        batch_op.add_column(
            sa.Column("prompt_version_id", sa.Uuid(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_agent_results_prompt_version",
            "prompt_versions",
            ["prompt_version_id"],
            ["version_id"],
        )


def downgrade():
    with op.batch_alter_table("agent_results") as batch_op:
        batch_op.drop_constraint("fk_agent_results_prompt_version", type_="foreignkey")
        batch_op.drop_column("prompt_version_id")
