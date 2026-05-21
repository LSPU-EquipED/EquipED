"""Admin service helpers for prompt-version lookup."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import desc
from sqlalchemy.exc import IntegrityError

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
]
