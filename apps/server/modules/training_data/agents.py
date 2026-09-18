"""Valid agent identifiers and validation for training data workflows."""

from __future__ import annotations

from typing import Literal

from server.modules.training_data.exceptions import InvalidAgentIdError

VALID_AGENT_IDS: frozenset[str] = frozenset({"sme", "coordinator", "gad", "itso"})

TrainingAgentId = Literal["sme", "coordinator", "gad", "itso"]


def validate_agent_id(agent_id: str) -> str:
    """Validate that agent_id is recognized for training workflows.

    Returns the agent_id unchanged if valid.
    Raises InvalidAgentIdError if agent_id is not in VALID_AGENT_IDS.
    """
    if agent_id not in VALID_AGENT_IDS:
        raise InvalidAgentIdError(f"unknown agent_id: {agent_id!r}")
    return agent_id


__all__ = ["VALID_AGENT_IDS", "TrainingAgentId", "validate_agent_id"]
