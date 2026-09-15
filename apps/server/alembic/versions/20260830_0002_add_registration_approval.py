"""Add faculty registration and account approval state."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260830_0002"
down_revision = "20260830_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    account_status = sa.Enum(
        "pending", "approved", "rejected", "suspended", name="account_status"
    )
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        account_status.create(bind, checkfirst=True)
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("faculty_id", sa.String(length=100), nullable=True)
        )
        batch_op.add_column(
            sa.Column("department", sa.String(length=300), nullable=True)
        )
        batch_op.add_column(sa.Column("program", sa.String(length=100), nullable=True))
        batch_op.add_column(
            sa.Column(
                "account_status",
                account_status,
                nullable=False,
                server_default="approved",
            )
        )
        batch_op.add_column(
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("reviewed_by", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_users_reviewed_by", "users", ["reviewed_by"], ["user_id"]
        )
    op.create_table(
        "pending_registrations",
        sa.Column("registration_id", sa.Uuid(), primary_key=True),
        sa.Column("existing_user_id", sa.Uuid(), nullable=True),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("email", sa.String(length=300), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("faculty_id", sa.String(length=100), nullable=False),
        sa.Column("department", sa.String(length=300), nullable=False),
        sa.Column("program", sa.String(length=100), nullable=False),
        sa.Column("otp_hash", sa.String(length=128), nullable=False),
        sa.Column("otp_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("otp_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("token_hash", name="uq_pending_registrations_token_hash"),
        sa.UniqueConstraint("email", name="uq_pending_registrations_email"),
        sa.ForeignKeyConstraint(
            ["existing_user_id"], ["users.user_id"], ondelete="CASCADE"
        ),
    )


def downgrade() -> None:
    op.drop_table("pending_registrations")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("fk_users_reviewed_by", type_="foreignkey")
        for column in (
            "reviewed_by",
            "reviewed_at",
            "approved_at",
            "account_status",
            "program",
            "department",
            "faculty_id",
        ):
            batch_op.drop_column(column)
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        sa.Enum(name="account_status").drop(bind, checkfirst=True)
