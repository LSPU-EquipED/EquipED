"""Migrate managed account emails to the LSPU domain and revoke sessions."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260830_0001"
down_revision = "20260829_0006"
branch_labels = None
depends_on = None

OLD_DOMAIN = "@example.com"
NEW_DOMAIN = "@lspu.edu.ph"
MAX_EMAIL_LENGTH = 40


def upgrade() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    users = sa.Table("users", metadata, autoload_with=bind)
    sessions = sa.Table("sessions", metadata, autoload_with=bind)

    matching_users = (
        bind.execute(
            sa.select(users.c.user_id, users.c.email).where(
                sa.func.lower(users.c.email).like(f"%{OLD_DOMAIN}")
            )
        )
        .mappings()
        .all()
    )

    planned_updates = {
        row["user_id"]: row["email"].strip().lower()[: -len(OLD_DOMAIN)] + NEW_DOMAIN
        for row in matching_users
    }

    if any(len(email) > MAX_EMAIL_LENGTH for email in planned_updates.values()):
        raise RuntimeError("Cannot migrate an account email longer than 40 characters")

    target_emails = set(planned_updates.values())
    if len(target_emails) != len(planned_updates):
        raise RuntimeError(
            "Cannot migrate account emails because target addresses collide"
        )
    existing_targets = {
        email.strip().lower()
        for email in bind.execute(
            sa.select(users.c.email).where(
                sa.func.lower(users.c.email).in_(target_emails)
            )
        ).scalars()
    }
    source_emails = {row["email"].strip().lower() for row in matching_users}
    conflicts = existing_targets - source_emails
    if conflicts:
        raise RuntimeError(
            "Cannot migrate account emails because target addresses already exist: "
            + ", ".join(sorted(conflicts))
        )

    for user_id, email in planned_updates.items():
        bind.execute(
            users.update().where(users.c.user_id == user_id).values(email=email)
        )

    bind.execute(
        sessions.update()
        .where(sessions.c.revoked_at.is_(None))
        .values(revoked_at=sa.func.now())
    )


def downgrade() -> None:
    raise RuntimeError("The account email migration is intentionally irreversible")
