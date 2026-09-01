"""Admin user management helpers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from server.modules.auth.email_policy import normalize_lspu_email
from server.modules.auth.models import AccountStatus, User, UserRole
from server.modules.auth.service import (
    create_user as auth_create_user,
)
from server.modules.auth.service import (
    revoke_active_sessions,
)
from sqlalchemy import select

__all__ = [
    "list_users",
    "create_admin_user",
    "update_user",
    "deactivate_user",
    "hard_delete_user",
]


def list_users(db: Any) -> list[User]:
    """Return all registered users."""
    stmt = select(User).order_by(User.created_at.desc())
    return list(db.scalars(stmt).all())


def create_admin_user(
    db: Any,
    *,
    name: str,
    email: str,
    password: str,
    role: str = "faculty",
) -> User:
    """Create a new user via the auth service.

    Re-uses the existing create_user logic for password hashing and persistence.
    """
    user_role = UserRole(role)
    return auth_create_user(
        db,
        name=name,
        email=normalize_lspu_email(email),
        password=password,
        role=user_role,
        is_active=True,
    )


def update_user(
    db: Any,
    user_id: uuid.UUID,
    *,
    name: str | None = None,
    email: str | None = None,
    is_active: bool | None = None,
    account_status: AccountStatus | None = None,
    reviewed_by: uuid.UUID | None = None,
) -> User:
    """Update an existing user by ID with row locking. Only provided fields are changed.

    Raises ValueError if the user is not found or the email is already taken.
    """
    stmt = select(User).where(User.user_id == user_id).with_for_update()
    user = db.scalar(stmt)
    if user is None:
        raise ValueError("User not found")

    normalized_email = normalize_lspu_email(email) if email is not None else None
    if normalized_email is not None and normalized_email != user.email:
        existing_stmt = select(User).where(User.email == normalized_email)
        existing = db.scalar(existing_stmt)
        if existing is not None:
            raise ValueError("Email already in use")
        user.email = normalized_email

    if name is not None:
        user.name = name

    previous_status = user.account_status
    user._previous_account_status = previous_status

    if account_status is not None:
        user.account_status = account_status
        user.is_active = account_status == AccountStatus.APPROVED
        user.reviewed_at = datetime.now(UTC)
        user.reviewed_by = reviewed_by
        user.approved_at = (
            datetime.now(UTC) if account_status == AccountStatus.APPROVED else None
        )
        if account_status in {AccountStatus.REJECTED, AccountStatus.SUSPENDED} or (
            previous_status == AccountStatus.APPROVED
            and account_status != AccountStatus.APPROVED
        ):
            revoke_active_sessions(db, user.user_id, revoked_at=user.reviewed_at)
    elif is_active is not None:
        user.is_active = is_active
        if not is_active:
            revoke_active_sessions(db, user.user_id, revoked_at=datetime.now(UTC))

    db.flush()
    return user


def deactivate_user(
    db: Any, user_id: uuid.UUID, *, reviewed_by: uuid.UUID | None = None
) -> User:
    """Deactivate a user account by setting account_status=SUSPENDED.

    Raises ValueError if the user is not found.
    """
    return update_user(
        db,
        user_id,
        account_status=AccountStatus.SUSPENDED,
        reviewed_by=reviewed_by,
    )


def hard_delete_user(db: Any, user_id: uuid.UUID) -> None:
    """Permanently delete a user from the database.

    Raises ValueError if the user is not found.
    """
    stmt = select(User).where(User.user_id == user_id).with_for_update()
    user = db.scalar(stmt)
    if user is None:
        raise ValueError("User not found")

    db.delete(user)
    db.flush()
