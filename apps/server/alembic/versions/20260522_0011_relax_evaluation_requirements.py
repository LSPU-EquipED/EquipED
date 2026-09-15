"""relax evaluation requirements — make syllabus/curriculum optional

Revision ID: 20260522_0011
Revises: 20260522_0010
Create Date: 2026-05-22
"""

from alembic import op


revision = "20260522_0011"
down_revision = "20260522_0010"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("evaluation_jobs") as batch_op:
        batch_op.alter_column("syllabus_id", nullable=True)
        batch_op.alter_column("curriculum_id", nullable=True)


def downgrade():
    with op.batch_alter_table("evaluation_jobs") as batch_op:
        batch_op.alter_column("syllabus_id", nullable=False)
        batch_op.alter_column("curriculum_id", nullable=False)
