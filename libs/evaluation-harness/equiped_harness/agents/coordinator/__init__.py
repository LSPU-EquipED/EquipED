"""Coordinator specialist implementation and capability metadata."""

__all__ = ["Coordinator"]


def __getattr__(name: str):
    if name == "Coordinator":
        from equiped_harness.agents.coordinator.agent import Coordinator

        return Coordinator
    raise AttributeError(name)
