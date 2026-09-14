"""Public lazy facade for agents module (PEP 562)."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "AdvisoryOutput",
    "AgentEvaluationResult",
    "Coordinator",
    "CriterionScore",
    "GAD",
    "ITSO",
    "SME",
    "Supervisor",
    "UngroundedCriterionAdvisory",
]

_FACADE_MAP: dict[str, tuple[str, str]] = {
    "AdvisoryOutput": ("server.modules.agents.contracts", "AdvisoryOutput"),
    "AgentEvaluationResult": (
        "server.modules.agents.contracts",
        "AgentEvaluationResult",
    ),
    "Coordinator": ("server.modules.agents.coordinator.agent", "Coordinator"),
    "CriterionScore": ("server.modules.agents.contracts", "CriterionScore"),
    "GAD": ("server.modules.agents.gad.agent", "GAD"),
    "ITSO": ("server.modules.agents.itso.agent", "ITSO"),
    "SME": ("server.modules.agents.sme.agent", "SME"),
    "Supervisor": ("server.modules.agents.supervision.supervisor", "Supervisor"),
    "UngroundedCriterionAdvisory": (
        "server.modules.agents.contracts",
        "UngroundedCriterionAdvisory",
    ),
}


def __getattr__(name: str) -> Any:
    target = _FACADE_MAP.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    mod_path, attr_name = target
    module = importlib.import_module(mod_path)
    val = getattr(module, attr_name)
    globals()[name] = val
    return val


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + __all__)
