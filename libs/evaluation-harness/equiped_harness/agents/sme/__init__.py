"""SME specialist implementation and capability metadata."""

__all__ = ["SME"]


def __getattr__(name: str):
    if name == "SME":
        from equiped_harness.agents.sme.agent import SME

        return SME
    raise AttributeError(name)
