"""Restore reviewed training sources without replacing existing job snapshots.

Revision ID: 20261019_0001
Revises: 20261015_0001
"""

import sqlalchemy as sa
from alembic import op

revision = "20261019_0001"
down_revision = "20261015_0001"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("dpo_training_jobs")}
    if "is_active_training_source" not in columns:
        op.add_column(
            "dpo_training_jobs",
            sa.Column(
                "is_active_training_source",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
    indexes = {index["name"] for index in inspector.get_indexes("dpo_training_jobs")}
    if "uq_dpo_training_jobs_active_source" not in indexes:
        op.create_index(
            "uq_dpo_training_jobs_active_source",
            "dpo_training_jobs",
            ["agent_id"],
            unique=True,
            postgresql_where=sa.column("is_active_training_source").is_(True),
            sqlite_where=sa.column("is_active_training_source").is_(True),
        )


def downgrade():
    op.drop_index("uq_dpo_training_jobs_active_source", table_name="dpo_training_jobs")
    op.drop_column("dpo_training_jobs", "is_active_training_source")
