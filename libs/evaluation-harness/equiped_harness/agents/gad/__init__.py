"""GAD specialist implementation and capability metadata."""

__all__ = ["GAD"]


def __getattr__(name: str):
    if name == "GAD":
        from equiped_harness.agents.gad.agent import GAD

        return GAD
    raise AttributeError(name)
