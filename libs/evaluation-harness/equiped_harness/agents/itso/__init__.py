"""ITSO specialist implementation and capability metadata."""

__all__ = ["ITSO"]


def __getattr__(name: str):
    if name == "ITSO":
        from equiped_harness.agents.itso.agent import ITSO

        return ITSO
    raise AttributeError(name)
