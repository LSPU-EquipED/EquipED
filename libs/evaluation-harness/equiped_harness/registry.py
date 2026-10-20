"""Resolve specialist implementations only when explicitly requested."""

from __future__ import annotations

AGENT_IDS = ("sme", "coordinator", "gad", "itso")


def get_agent_class(agent_id: str):
    if agent_id == "sme":
        from equiped_harness.agents.sme.agent import SME

        return SME
    if agent_id == "coordinator":
        from equiped_harness.agents.coordinator.agent import Coordinator

        return Coordinator
    if agent_id == "gad":
        from equiped_harness.agents.gad.agent import GAD

        return GAD
    if agent_id == "itso":
        from equiped_harness.agents.itso.agent import ITSO

        return ITSO
    raise ValueError("Unsupported specialist")


def specialist_classes() -> tuple[type, ...]:
    return tuple(get_agent_class(agent_id) for agent_id in AGENT_IDS)


def is_builtin_agent(agent) -> bool:
    name = getattr(agent, "agent_name", None)
    return name in AGENT_IDS and type(agent) is get_agent_class(name)
