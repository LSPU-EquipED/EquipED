"""Preserve curriculum identities while enabling audited administrator editing."""

import sqlalchemy as sa

from alembic import op

revision = "20261023_0001"
down_revision = "20261020_0003"
branch_labels = None
depends_on = None

PROGRAM_KEY = (
    "CASE WHEN upper(trim(program)) IN ('BSIT', 'BSINFOTECH') "
    "THEN 'BSInfoTech' ELSE upper(trim(program)) END"
)


def upgrade():
    duplicates = (
        op.get_bind()
        .execute(
            sa.text(
                f"SELECT upper(trim(code)), {PROGRAM_KEY}, count(*) "
                "FROM curriculum_objectives "
                f"GROUP BY upper(trim(code)), {PROGRAM_KEY} HAVING count(*) > 1"
            )
        )
        .first()
    )
    if duplicates:
        raise RuntimeError(
            "Resolve duplicate curriculum codes/program aliases before migrating."
        )
    if op.get_bind().scalar(
        sa.text(
            "SELECT count(*) FROM curriculum_objectives "
            "WHERE length(description) > 4000"
        )
    ):
        raise RuntimeError(
            "Review objective descriptions over 4000 characters before migrating."
        )
    with op.batch_alter_table("courses") as batch:
        batch.add_column(
            sa.Column(
                "mapping_version", sa.Integer(), nullable=False, server_default="1"
            )
        )
        batch.add_column(
            sa.Column(
                "mappings_managed",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
    with op.batch_alter_table("curriculum_objectives") as batch:
        batch.add_column(
            sa.Column("version", sa.Integer(), nullable=False, server_default="1")
        )
        batch.add_column(
            sa.Column(
                "managed_by_admin",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch.add_column(sa.Column("seed_code", sa.String(50), nullable=True))
        batch.create_unique_constraint(
            "uq_curriculum_objectives_seed_code", ["seed_code"]
        )
    # Anchor the original institutional seed rows before any admin can rename
    # their code/program. Subsequent seeds resolve by this immutable seed key.
    op.get_bind().execute(
        sa.text(
            "UPDATE curriculum_objectives SET seed_code = upper(trim(code)) "
            "WHERE upper(trim(program)) IN ('BSINFOTECH', 'BSIT') "
            "AND upper(trim(code)) IN ('IT01','IT02','IT03','IT04','IT05','IT06',"
            "'IT07','IT08','IT09','IT10','IT11','IT12')"
        )
    )
    op.create_index(
        "uq_curriculum_objective_normalized",
        "curriculum_objectives",
        [sa.text("upper(trim(code))"), sa.text(f"({PROGRAM_KEY})")],
        unique=True,
    )
    op.create_table(
        "curriculum_changes",
        sa.Column("change_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "actor_id",
            sa.Uuid(),
            sa.ForeignKey("users.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("before", sa.JSON(), nullable=True),
        sa.Column("after", sa.JSON(), nullable=False),
    )


def downgrade():
    op.drop_table("curriculum_changes")
    op.drop_index(
        "uq_curriculum_objective_normalized", table_name="curriculum_objectives"
    )
    with op.batch_alter_table("curriculum_objectives") as batch:
        batch.drop_constraint("uq_curriculum_objectives_seed_code", type_="unique")
        for name in ("seed_code", "managed_by_admin", "version"):
            batch.drop_column(name)
    with op.batch_alter_table("courses") as batch:
        batch.drop_column("mappings_managed")
        batch.drop_column("mapping_version")
