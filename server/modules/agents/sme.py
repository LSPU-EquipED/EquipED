"""SME domain agent."""

from __future__ import annotations

from .base import BaseAgent


class SME(BaseAgent):
    agent_name = "sme"
    rubric_source_type = "rubric_sme"


SMEAgent = SME


__all__ = ["SME", "SMEAgent"]
