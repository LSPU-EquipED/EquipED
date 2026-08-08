"""Admin user management helpers."""

from __future__ import annotations

import uuid
from typing import Any

from server.modules.auth.models import User, UserRole
from server.modules.auth.service import create_user as auth_create_user

__all__ = [
    "list_users",
    "create_admin_user",
    "update_user",
    "deactivate_user",
    "hard_delete_user",
]


def list_users(db: Any) -> list[User]:
    """Return all registered users."""
    return db.query(User).order_by(User.created_at.desc()).all()


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
        email=email,
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
) -> User:
    """Update an existing user by ID. Only provided (non-None) fields are changed.

    Raises ValueError if the user is not found or the email is already taken.
    """
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise ValueError("User not found")

    if email is not None and email != user.email:
        existing = db.query(User).filter(User.email == email).first()
        if existing is not None:
            raise ValueError("Email already in use")
        user.email = email

    if name is not None:
        user.name = name

    if is_active is not None:
        user.is_active = is_active

    db.flush()
    return user


def deactivate_user(db: Any, user_id: uuid.UUID) -> User:
    """Deactivate a user account by setting is_active=False.

    Raises ValueError if the user is not found.
    """
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise ValueError("User not found")

    user.is_active = False
    db.flush()
    return user


def hard_delete_user(db: Any, user_id: uuid.UUID) -> None:
    """Permanently delete a user from the database.

    Raises ValueError if the user is not found.
    """
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise ValueError("User not found")

    db.delete(user)
    db.flush()
