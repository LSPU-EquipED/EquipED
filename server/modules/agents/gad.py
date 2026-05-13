"""GAD domain agent."""

from __future__ import annotations

from .base import BaseAgent


class GAD(BaseAgent):
    agent_name = "gad"
    rubric_source_type = "rubric_gad"


GADAgent = GAD


__all__ = ["GAD", "GADAgent"]
