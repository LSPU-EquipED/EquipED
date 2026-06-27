"""Admin service helpers for prompt-version lookup, user management, and system metrics."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import desc, func
from sqlalchemy.exc import IntegrityError

from server.modules.auth.models import User, UserRole
from server.modules.auth.service import create_user as auth_create_user
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus

from .models import PromptVersion
from server.modules.feedback.service import list_preference_logs

VALID_AGENTS = {"sme", "coordinator", "gad", "itso"}


def get_active_prompt(agent_id: str, db: Any) -> PromptVersion:
    """Return the active prompt version for an agent.

    Raises a ValueError when no active version exists so callers fail closed.
    """

    if agent_id not in VALID_AGENTS:
        raise ValueError(f"Unknown agent_id: {agent_id}")

    row = (
        db.query(PromptVersion)
        .filter(
            PromptVersion.agent_id == agent_id,
            PromptVersion.is_active.is_(True),
        )
        .order_by(PromptVersion.version_number.desc())
        .first()
    )
    if row is None:
        raise ValueError(f"No active prompt version found for agent {agent_id}")
    return row


def list_prompt_versions(agent_id: str, db) -> list[PromptVersion]:
    """Return all prompt versions for an agent, newest first."""

    if agent_id not in VALID_AGENTS:
        raise ValueError(f"Unknown agent_id: {agent_id}")
    return (
        db.query(PromptVersion)
        .filter(PromptVersion.agent_id == agent_id)
        .order_by(desc(PromptVersion.version_number))
        .all()
    )


def create_prompt_version(
    agent_id: str,
    prompt_text: str,
    updated_by: str | uuid.UUID,
    motivation: str | None = None,
    db=None,
) -> PromptVersion:
    """Create a new active prompt version. Deactivates all other versions."""

    if agent_id not in VALID_AGENTS:
        raise ValueError(f"Unknown agent_id: {agent_id}")
    if not prompt_text or not prompt_text.strip():
        raise ValueError("prompt_text must not be empty")

    db.query(PromptVersion).filter(PromptVersion.agent_id == agent_id).with_for_update().all()

    highest = (
        db.query(PromptVersion.version_number)
        .filter(PromptVersion.agent_id == agent_id)
        .order_by(desc(PromptVersion.version_number))
        .first()
    )
    next_version = (highest[0] + 1) if highest else 1

    db.query(PromptVersion).filter(
        PromptVersion.agent_id == agent_id,
        PromptVersion.is_active == True,
    ).update({"is_active": False})

    new_prompt = PromptVersion(
        agent_id=agent_id,
        version_number=next_version,
        prompt_text=prompt_text.strip(),
        is_active=True,
        updated_by=updated_by,
        motivation=motivation,
    )
    try:
        db.add(new_prompt)
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError(
            f"Concurrent modification detected for agent {agent_id}. Please retry."
        ) from exc
    return new_prompt


def revert_prompt_version(
    agent_id: str,
    version_id: str | uuid.UUID,
    updated_by: str | uuid.UUID,
    db=None,
) -> PromptVersion:
    """Clone an older prompt version as a new active version."""

    if agent_id not in VALID_AGENTS:
        raise ValueError(f"Unknown agent_id: {agent_id}")

    source = (
        db.query(PromptVersion)
        .filter(
            PromptVersion.agent_id == agent_id,
            PromptVersion.version_id == version_id,
        )
        .first()
    )
    if not source:
        raise ValueError(f"Version {version_id} not found for agent {agent_id}")

    db.query(PromptVersion).filter(PromptVersion.agent_id == agent_id).with_for_update().all()

    db.query(PromptVersion).filter(
        PromptVersion.agent_id == agent_id,
        PromptVersion.is_active == True,
    ).update({"is_active": False})

    highest = (
        db.query(PromptVersion.version_number)
        .filter(PromptVersion.agent_id == agent_id)
        .order_by(desc(PromptVersion.version_number))
        .first()
    )
    next_version = (highest[0] + 1) if highest else 1

    new_prompt = PromptVersion(
        agent_id=agent_id,
        version_number=next_version,
        prompt_text=source.prompt_text,
        is_active=True,
        updated_by=updated_by,
        motivation=f"Reverted to version {source.version_number}",
    )
    try:
        db.add(new_prompt)
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError(
            f"Concurrent modification detected for agent {agent_id}. Please retry."
        ) from exc
    return new_prompt


__all__ = [
    "get_active_prompt",
    "list_prompt_versions",
    "create_prompt_version",
    "revert_prompt_version",
    "list_preference_logs",
    "list_users",
    "create_admin_user",
    "update_user",
    "deactivate_user",
    "hard_delete_user",
    "get_system_summary",
]


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# System metrics
# ---------------------------------------------------------------------------

_TERMINAL_STATUSES = {
    EvaluationStatus.COMPLETED.value,
    EvaluationStatus.FAILED.value,
}


def get_system_summary(db: Any) -> dict[str, int]:
    """Return system-wide counts for the admin dashboard."""
    from server.modules.documents.models import Document

    total_documents = db.query(func.count()).select_from(Document).scalar() or 0

    total_faculty = db.query(func.count()).select_from(User).filter(
        User.role == UserRole.FACULTY
    ).scalar() or 0

    active_evaluations = db.query(func.count()).select_from(EvaluationJob).filter(
        EvaluationJob.status.not_in(_TERMINAL_STATUSES)
    ).scalar() or 0

    failed_evaluations = db.query(func.count()).select_from(EvaluationJob).filter(
        EvaluationJob.status == EvaluationStatus.FAILED.value
    ).scalar() or 0

    return {
        "total_documents": total_documents,
        "total_faculty": total_faculty,
        "active_evaluations": active_evaluations,
        "failed_evaluations": failed_evaluations,
    }
