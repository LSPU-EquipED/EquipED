"""ITSO domain agent."""

from __future__ import annotations

from .base import BaseAgent


class ITSO(BaseAgent):
    agent_name = "itso"
    rubric_source_type = "rubric_itso"
    domain_keywords = (
        "security", "privacy", "data", "protection", "encryption",
        "authentication", "threat", "vulnerability", "confidential",
        "integrity", "access control", "risk",
    )


ITSOAgent = ITSO


__all__ = ["ITSO", "ITSOAgent"]
