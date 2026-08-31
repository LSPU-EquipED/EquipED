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
    op.add_column(
        "users", sa.Column("faculty_id", sa.String(length=100), nullable=True)
    )
    op.add_column(
        "users", sa.Column("department", sa.String(length=300), nullable=True)
    )
    op.add_column("users", sa.Column("program", sa.String(length=100), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "account_status", account_status, nullable=False, server_default="approved"
        ),
    )
    op.add_column(
        "users", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "users", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("users", sa.Column("reviewed_by", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_users_reviewed_by", "users", "users", ["reviewed_by"], ["user_id"]
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
    op.drop_constraint("fk_users_reviewed_by", "users", type_="foreignkey")
    for column in (
        "reviewed_by",
        "reviewed_at",
        "approved_at",
        "account_status",
        "program",
        "department",
        "faculty_id",
    ):
        op.drop_column("users", column)
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        sa.Enum(name="account_status").drop(bind, checkfirst=True)
