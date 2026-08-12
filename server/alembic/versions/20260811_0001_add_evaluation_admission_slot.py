"""Add the single evaluation admission slot."""

import sqlalchemy as sa

from alembic import op

revision = "20260811_0001"
down_revision = "20260810_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("evaluation_jobs") as batch:
        batch.add_column(sa.Column("admission_slot", sa.SmallInteger(), nullable=True))
        batch.create_check_constraint(
            "ck_evaluation_admission_slot",
            "admission_slot IS NULL OR admission_slot = 1",
        )
        batch.create_unique_constraint(
            "uq_evaluation_admission_slot", ["admission_slot"]
        )
    op.create_index(
        "idx_jobs_admission_fifo",
        "evaluation_jobs",
        ["status", "submitted_at", "evaluation_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_jobs_admission_fifo", table_name="evaluation_jobs")
    with op.batch_alter_table("evaluation_jobs") as batch:
        batch.drop_constraint("uq_evaluation_admission_slot", type_="unique")
        batch.drop_constraint("ck_evaluation_admission_slot", type_="check")
        batch.drop_column("admission_slot")
