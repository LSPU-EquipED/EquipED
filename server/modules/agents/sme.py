"""SME domain agent."""

from __future__ import annotations

from .base import BaseAgent


class SME(BaseAgent):
    agent_name = "sme"
    rubric_source_type = "rubric_sme"
    domain_keywords = (
        "accuracy", "content", "knowledge", "concepts", "theory",
        "definitions", "principles", "facts", "understanding", "correct",
    )


SMEAgent = SME


__all__ = ["SME", "SMEAgent"]
