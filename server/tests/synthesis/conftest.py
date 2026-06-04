"""Shared fakes and fixtures for synthesis module tests."""

from __future__ import annotations


def make_agent_result(
    agent_name: str,
    overall_score: float,
    status: str = "completed",
):
    """Build a lightweight AgentResult-like object for testing."""

    class FakeAgentResult:
        def __init__(self, agent_name, subtotal, status):
            self.agent_name = agent_name
            self.subtotal = subtotal
            self.success = status == "completed"
            self.error_message = None if self.success else "failed"

    return FakeAgentResult(agent_name, overall_score, status)


def make_scored_agent(agent_id: str, subtotal: float, criteria_count: int = 1):
    result = make_agent_result(agent_id, float(subtotal), status="completed")
    return result
