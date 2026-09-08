"""Canonical schedule definition for evaluation agents."""

from __future__ import annotations

FULL_SCHEDULED_AGENT_IDS: tuple[str, ...] = ("sme", "coordinator", "gad", "itso")
PARTIAL_WITHOUT_CURRICULUM_SCHEDULED_AGENT_IDS: tuple[str, ...] = (
    "sme",
    "gad",
    "itso",
)

VALID_TARGET_AGENTS: tuple[str, ...] = ("sme", "coordinator", "gad", "itso")


def scheduled_agent_ids(
    *,
    target_agent: str | None = None,
    partial_without_curriculum: bool | None = None,
) -> tuple[str, ...]:
    """Return canonical scheduled agent IDs.

    Targeted single-agent flow takes precedence: a valid ``target_agent``
    resolves to ``(target_agent,)`` and the historical ``"all"`` bundle
    resolves to the full 4-agent schedule. The legacy
    ``partial_without_curriculum`` flag is retained for historical jobs and
    tests that construct ``EvaluationJob`` rows directly.
    """
    if target_agent is not None:
        if target_agent == "all":
            return FULL_SCHEDULED_AGENT_IDS
        if target_agent in VALID_TARGET_AGENTS:
            return (target_agent,)
        raise ValueError(f"Unknown target_agent: {target_agent}")
    if partial_without_curriculum is not None:
        if partial_without_curriculum:
            return PARTIAL_WITHOUT_CURRICULUM_SCHEDULED_AGENT_IDS
        return FULL_SCHEDULED_AGENT_IDS
    return FULL_SCHEDULED_AGENT_IDS


__all__ = [
    "FULL_SCHEDULED_AGENT_IDS",
    "PARTIAL_WITHOUT_CURRICULUM_SCHEDULED_AGENT_IDS",
    "VALID_TARGET_AGENTS",
    "scheduled_agent_ids",
]
