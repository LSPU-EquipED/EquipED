"""Program coordinator domain agent."""

from __future__ import annotations

from .base import BaseAgent


class Coordinator(BaseAgent):
    agent_name = "coordinator"
    rubric_source_type = "rubric_coord"
    reference_source_types = ("syllabus",)


ProgramCoordinator = Coordinator


__all__ = ["Coordinator", "ProgramCoordinator"]
