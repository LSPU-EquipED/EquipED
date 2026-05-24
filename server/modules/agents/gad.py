"""GAD domain agent."""

from __future__ import annotations

from .base import BaseAgent


class GAD(BaseAgent):
    agent_name = "gad"
    rubric_source_type = "rubric_gad"
    domain_keywords = (
        "gender", "inclusion", "diversity", "equity", "accessibility",
        "representation", "inclusive", "fair", "bias", "equal",
        "marginalized", "sensitivity",
    )


GADAgent = GAD


__all__ = ["GAD", "GADAgent"]
