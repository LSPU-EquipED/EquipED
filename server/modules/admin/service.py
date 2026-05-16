"""Admin service helpers for prompt-version lookup."""

from __future__ import annotations

from typing import Any

from .models import PromptVersion


def get_active_prompt(agent_id: str, db: Any) -> PromptVersion:
    """Return the active prompt version for an agent.

    Raises a ValueError when no active version exists so callers fail closed.
    """

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


__all__ = ["get_active_prompt"]
