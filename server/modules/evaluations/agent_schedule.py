"""Canonical schedule definition for evaluation agents."""

from __future__ import annotations

FULL_SCHEDULED_AGENT_IDS: tuple[str, ...] = ("sme", "coordinator", "gad", "itso")
PARTIAL_WITHOUT_CURRICULUM_SCHEDULED_AGENT_IDS: tuple[str, ...] = (
    "sme",
    "gad",
    "itso",
)


def scheduled_agent_ids(*, partial_without_curriculum: bool) -> tuple[str, ...]:
    """Return canonical scheduled agent IDs for the evaluation mode."""
    if partial_without_curriculum:
        return PARTIAL_WITHOUT_CURRICULUM_SCHEDULED_AGENT_IDS
    return FULL_SCHEDULED_AGENT_IDS


__all__ = [
    "FULL_SCHEDULED_AGENT_IDS",
    "PARTIAL_WITHOUT_CURRICULUM_SCHEDULED_AGENT_IDS",
    "scheduled_agent_ids",
]
